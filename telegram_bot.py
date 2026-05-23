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
예: 삼성전자 2024 텍스트

지원 단위: 원, 천원, 백만원, 억원, 조원"""

UNIT_WORDS = ("백만원", "천원", "억원", "조원", "원", "억", "조", "won", "thousand", "million", "eok", "trillion")


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
            text_result = build_report_text_result(require_api_key(), company, years[-1], limit=450)
        except Exception as exc:
            await update.message.reply_text(f"텍스트 조회 실패: {exc}")
            return
        labels = {
            "company_overview": "회사의 개요",
            "business_overview": "사업의 내용",
            "business_summary": "사업의 개요",
            "products_services": "주요 제품 및 서비스",
            "sales_orders": "매출 및 수주상황",
            "research_development": "연구개발활동",
        }
        sections = text_result.get("sections", {})
        if sections:
            lines = [f"{company} {years[-1]}년 사업보고서 텍스트"]
            for key, value in sections.items():
                lines.append(f"\n[{labels.get(key, key)}]\n{value}")
            await update.message.reply_text("\n".join(lines)[:3900])
        else:
            await update.message.reply_text("추출된 주요 텍스트 섹션이 없습니다.")


def main() -> int:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN 환경변수를 설정하세요.")
    require_api_key()

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
