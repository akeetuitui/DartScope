from __future__ import annotations

import os
import re

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from dart_financials import (
    AMOUNT_UNITS,
    build_comparison_result,
    build_report_text_result,
    format_comparison_message,
    normalize_amount_unit,
    require_api_key,
)

USAGE = """DartScope 봇 사용법

기업명과 사업연도를 보내주세요.
예: 삼성전자 2024
예: 삼성전자 2022 2023 2024
예: 삼성전자 2022 2023 2024 단위 백만원

사업보고서 텍스트:
/report 삼성전자 2024
/business 삼성전자 2024

맥북에서 봇 켜는 법:
/mac

지원 단위: 원, 천원, 백만원, 억원, 조원"""

UNIT_WORDS = ("백만원", "천원", "억원", "조원", "원", "억", "조", "won", "thousand", "million", "eok", "trillion")

MAC_HELP = """맥북에서 텔레그램 봇 켜는 명령어

cd "/Users/akee/Documents/DartScope"
export DART_API_KEY="실제_DART_API_KEY"
export TELEGRAM_BOT_TOKEN="실제_텔레그램_봇_토큰"
.venv/bin/python telegram_bot.py

실행 후 터미널이 멈춘 것처럼 보이면 정상입니다. 봇이 메시지를 기다리는 중입니다. 끄려면 Control + C를 누르세요."""


def parse_message(text: str) -> tuple[str, list[str], str, bool] | None:
    clean_text = text.strip()
    include_text = any(word in clean_text for word in ("텍스트", "사업내용", "사업소개", "원문"))
    years = re.findall(r"(?:19|20)\d{2}", clean_text)
    if not years:
        return None

    first_year = clean_text.find(years[0])
    unit_area = clean_text[first_year:]
    amount_unit = "eok"
    for word in UNIT_WORDS:
        if re.search(rf"(?:단위\s*){re.escape(word)}|\b{re.escape(word)}\b", unit_area, flags=re.IGNORECASE):
            amount_unit = normalize_amount_unit(word)
            break

    company = clean_text[:first_year].strip(" ,/")
    if not company:
        return None

    unique_years = []
    for year in years:
        if year not in unique_years:
            unique_years.append(year)
    return company, unique_years, amount_unit, include_text


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    await update.message.reply_text(USAGE)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    await update.message.reply_text(USAGE)


async def mac_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    await update.message.reply_text(MAC_HELP)


BUSINESS_BRIEF_SECTIONS = (
    ("business_summary", "사업구조"),
    ("business_overview", "사업내용"),
    ("products_services", "제품/매출"),
    ("sales_orders", "가격/원재료/수주"),
    ("research_development", "R&D/주요계약"),
    ("future_strategy", "향후전략"),
    ("risk_management", "위험관리"),
    ("management_discussion", "경영진단"),
)


def clean_report_text(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip()
    cleaned = re.sub(r"^(회사의 개요|사업의 내용|사업의 개요|주요 제품 및 서비스|매출 및 수주상황|연구개발활동|위험관리(?: 및 파생거래)?|이사의 경영진단 및 분석의견)\s*", "", cleaned)
    cleaned = re.sub(r"[☞※].*?(?=\. |$)", "", cleaned)
    cleaned = re.sub(r"\(단위 ?: ?[^)]*\)", "", cleaned)
    cleaned = re.sub(r"\b[가-하]\. ", "", cleaned)
    cleaned = re.sub(r"^(및 파생거래|주요 제품 매출)\s*", "", cleaned)
    return cleaned.strip(" -:")


def brief_sentences(value: str, max_sentences: int = 2, max_chars: int = 230) -> str:
    cleaned = clean_report_text(value)
    if not cleaned:
        return "-"
    sentences = re.split(r"(?<=[.!?다요음임됨함])\s+", cleaned)
    picked = []
    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 18:
            continue
        if any(noise in sentence for noise in ("항목을 참고", "다음과 같습니다", "표 ", "부 문 주요 제품")):
            continue
        picked.append(sentence)
        if len(picked) >= max_sentences:
            break
    summary = " ".join(picked) if picked else cleaned
    return summary[:max_chars].rstrip() + ("..." if len(summary) > max_chars else "")


def format_text_sections_message(company: str, year: str, text_result: dict[str, object]) -> str:
    sections = text_result.get("sections", {})
    if not sections:
        return "추출된 주요 텍스트 섹션이 없습니다."

    lines = [f"{company} {year}년 사업보고서 브리핑"]
    for key, label in BUSINESS_BRIEF_SECTIONS:
        value = sections.get(key)
        if value:
            lines.append(f"\n[{label}]\n{brief_sentences(str(value))}")

    if len(lines) == 1:
        lines.append("\n추출된 주요 텍스트 섹션이 없습니다.")
    return "\n".join(lines)[:3900]


def parse_business_args(text: str) -> tuple[str, str] | None:
    cleaned = re.sub(r"^/(?:business|report)\s*", "", text.strip(), flags=re.IGNORECASE)
    years = re.findall(r"(?:19|20)\d{2}", cleaned)
    if not years:
        return None
    first_year = cleaned.find(years[0])
    company = cleaned[:first_year].strip(" ,/")
    if not company:
        return None
    return company, years[-1]


async def business_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    parsed = parse_business_args(update.message.text or "")
    if not parsed:
        await update.message.reply_text("사용법: /business 삼성전자 2024 또는 /report 삼성전자 2024")
        return
    company, year = parsed
    await update.message.reply_text("사업보고서 텍스트를 조회하는 중입니다...")
    try:
        text_result = build_report_text_result(require_api_key(), company, year, limit=550)
    except Exception as exc:
        await update.message.reply_text(f"텍스트 조회 실패: {exc}")
        return
    await update.message.reply_text(format_text_sections_message(company, year, text_result))


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    parsed = parse_message(update.message.text or "")
    if not parsed:
        await update.message.reply_text(USAGE)
        return

    company, years, amount_unit, include_text = parsed
    await update.message.reply_text("DART 사업보고서를 조회하는 중입니다...")
    try:
        comparison = build_comparison_result(require_api_key(), company, years, "CFS")
    except Exception as exc:
        await update.message.reply_text(f"조회 실패: {exc}")
        return

    await update.message.reply_text(format_comparison_message(comparison, amount_unit=amount_unit))

    if include_text:
        try:
            text_result = build_report_text_result(require_api_key(), company, years[-1], limit=550)
        except Exception as exc:
            await update.message.reply_text(f"텍스트 조회 실패: {exc}")
            return
        await update.message.reply_text(format_text_sections_message(company, years[-1], text_result))


def main() -> int:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN 환경변수를 설정하세요.")
    require_api_key()

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("mac", mac_command))
    app.add_handler(CommandHandler("business", business_command))
    app.add_handler(CommandHandler("report", business_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
