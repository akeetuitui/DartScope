from __future__ import annotations

import os
import re

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from dart_financials import build_comparison_result, format_comparison_message, require_api_key

USAGE = "기업명과 사업연도를 보내주세요. 예: 삼성전자 2024 또는 삼성전자 2022 2023 2024"


def parse_message(text: str) -> tuple[str, list[str]] | None:
    years = re.findall(r"(?:19|20)\d{2}", text)
    if not years:
        return None
    first_year = text.find(years[0])
    company = text[:first_year].strip(" ,/")
    if not company:
        return None
    unique_years = []
    for year in years:
        if year not in unique_years:
            unique_years.append(year)
    return company, unique_years


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    await update.message.reply_text(f"DartScope 봇입니다.\n{USAGE}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    parsed = parse_message(update.message.text or "")
    if not parsed:
        await update.message.reply_text(USAGE)
        return

    company, years = parsed
    await update.message.reply_text("DART 사업보고서를 조회하는 중입니다...")
    try:
        comparison = build_comparison_result(require_api_key(), company, years, "CFS")
    except Exception as exc:
        await update.message.reply_text(f"조회 실패: {exc}")
        return

    await update.message.reply_text(format_comparison_message(comparison))


def main() -> int:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN 환경변수를 설정하세요.")
    require_api_key()

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
