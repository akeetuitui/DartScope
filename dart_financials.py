#!/usr/bin/env python3
"""Extract financial metrics from DART annual reports."""

from __future__ import annotations

import argparse
import csv
import html
import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


API_BASE = "https://opendart.fss.or.kr/api"
REPORT_ANNUAL = "11011"
CORP_CACHE = Path(".dart_cache/corp_codes.xml")

DISPLAY_METRICS = (
    "revenue",
    "cost_of_sales",
    "gross_profit",
    "gross_margin_pct",
    "cost_of_sales_ratio_pct",
    "selling_general_admin_expenses",
    "sga_ratio_pct",
    "operating_income",
    "operating_margin_pct",
    "profit_before_tax",
    "net_income",
    "net_margin_pct",
    "income_tax_expense",
    "basic_eps",
    "operating_cash_flow",
    "cash_and_cash_equivalents",
    "current_assets",
    "current_liabilities",
    "total_assets",
    "total_liabilities",
    "total_equity",
    "debt_ratio_pct",
    "current_ratio_pct",
    "roe_pct",
    "roa_pct",
)


METRIC_LABELS = {
    "revenue": "매출액",
    "cost_of_sales": "매출원가",
    "gross_profit": "매출총이익",
    "gross_margin_pct": "매출총이익률",
    "cost_of_sales_ratio_pct": "매출원가율",
    "selling_general_admin_expenses": "판매비와관리비",
    "sga_ratio_pct": "판관비율",
    "operating_income": "영업이익",
    "profit_before_tax": "법인세차감전순이익",
    "net_income": "당기순이익",
    "income_tax_expense": "법인세비용",
    "basic_eps": "기본주당이익",
    "operating_cash_flow": "영업활동현금흐름",
    "cash_and_cash_equivalents": "현금및현금성자산",
    "current_assets": "유동자산",
    "current_liabilities": "유동부채",
    "total_assets": "자산총계",
    "total_liabilities": "부채총계",
    "total_equity": "자본총계",
    "operating_margin_pct": "영업이익률",
    "net_margin_pct": "순이익률",
    "debt_ratio_pct": "부채비율",
    "current_ratio_pct": "유동비율",
    "roe_pct": "ROE",
    "roa_pct": "ROA",
}

AMOUNT_METRICS = {
    "revenue",
    "cost_of_sales",
    "gross_profit",
    "selling_general_admin_expenses",
    "operating_income",
    "profit_before_tax",
    "net_income",
    "income_tax_expense",
    "operating_cash_flow",
    "cash_and_cash_equivalents",
    "current_assets",
    "current_liabilities",
    "total_assets",
    "total_liabilities",
    "total_equity",
}

PER_SHARE_METRICS = {"basic_eps"}

AMOUNT_UNITS = {
    "won": {"label": "원", "divisor": 1},
    "thousand": {"label": "천원", "divisor": 1_000},
    "million": {"label": "백만원", "divisor": 1_000_000},
    "eok": {"label": "억원", "divisor": 100_000_000},
    "trillion": {"label": "조원", "divisor": 1_000_000_000_000},
}

UNIT_ALIASES = {
    "원": "won",
    "won": "won",
    "천원": "thousand",
    "thousand": "thousand",
    "백만원": "million",
    "million": "million",
    "억원": "eok",
    "억": "eok",
    "eok": "eok",
    "조원": "trillion",
    "조": "trillion",
    "trillion": "trillion",
}


@dataclass(frozen=True)
class Corp:
    corp_code: str
    corp_name: str
    stock_code: str
    modify_date: str


def request_json(path: str, params: dict[str, str]) -> dict[str, Any]:
    url = f"{API_BASE}/{path}.json?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    status = payload.get("status")
    if status and status != "000":
        message = payload.get("message", "DART API error")
        raise RuntimeError(f"DART API error {status}: {message}")
    return payload


def request_binary(path: str, params: dict[str, str], timeout: int = 60) -> bytes:
    url = f"{API_BASE}/{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read()


def download_corp_codes(api_key: str, cache_path: Path = CORP_CACHE) -> Path:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    url = f"{API_BASE}/corpCode.xml?{urllib.parse.urlencode({'crtfc_key': api_key})}"
    print("DART 기업코드 목록을 다운로드하는 중입니다...", file=sys.stderr)
    with urllib.request.urlopen(url, timeout=60) as response:
        blob = response.read()

    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        xml_name = archive.namelist()[0]
        cache_path.write_bytes(archive.read(xml_name))
    print(f"기업코드 캐시 저장 완료: {cache_path}", file=sys.stderr)
    return cache_path


def load_corps(api_key: str, refresh: bool = False) -> list[Corp]:
    if refresh or not CORP_CACHE.exists():
        download_corp_codes(api_key)

    root = ET.fromstring(CORP_CACHE.read_text(encoding="utf-8"))
    corps: list[Corp] = []
    for item in root.findall("list"):
        corps.append(
            Corp(
                corp_code=(item.findtext("corp_code") or "").strip(),
                corp_name=(item.findtext("corp_name") or "").strip(),
                stock_code=(item.findtext("stock_code") or "").strip(),
                modify_date=(item.findtext("modify_date") or "").strip(),
            )
        )
    return corps


def resolve_corp(api_key: str, query: str, refresh: bool = False) -> Corp:
    normalized = query.strip().lower()
    corps = load_corps(api_key, refresh=refresh)

    exact = [
        corp
        for corp in corps
        if corp.corp_name.lower() == normalized or corp.stock_code == query.strip()
    ]
    if exact:
        listed = [corp for corp in exact if corp.stock_code]
        return listed[0] if listed else exact[0]

    contains = [
        corp
        for corp in corps
        if normalized in corp.corp_name.lower() or query.strip() in corp.stock_code
    ]
    if len(contains) == 1:
        return contains[0]
    if contains:
        sample = "\n".join(
            f"- {corp.corp_name} / corp_code={corp.corp_code} / stock_code={corp.stock_code or '-'}"
            for corp in contains[:10]
        )
        raise RuntimeError(f"기업명이 여러 개 검색됐습니다. 더 정확히 입력하세요.\n{sample}")

    raise RuntimeError(f"기업을 찾지 못했습니다: {query}")


def parse_amount(value: str | None) -> Decimal | None:
    if not value or value.strip() in {"", "-"}:
        return None
    cleaned = value.replace(",", "").strip()
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def amount_to_number(value: Decimal | None) -> int | float | None:
    if value is None:
        return None
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def pick_account(
    rows: list[dict[str, Any]],
    statement: str | tuple[str, ...],
    account_ids: set[str],
    names: set[str],
) -> Decimal | None:
    statements = {statement} if isinstance(statement, str) else set(statement)
    candidates = []
    for row in rows:
        if row.get("sj_div") not in statements:
            continue
        account_id = str(row.get("account_id", ""))
        account_name = str(row.get("account_nm", ""))
        if account_id in account_ids or account_name in names:
            candidates.append(row)

    for key in ("thstrm_amount", "thstrm_add_amount"):
        for row in candidates:
            value = parse_amount(row.get(key))
            if value is not None:
                return value
    return None


def safe_ratio(numerator: Decimal | None, denominator: Decimal | None, scale: Decimal = Decimal("100")) -> Decimal | None:
    if numerator is None or denominator in (None, Decimal("0")):
        return None
    return (numerator / denominator * scale).quantize(Decimal("0.01"))


def get_financial_rows(api_key: str, corp_code: str, year: str, fs_div: str) -> list[dict[str, Any]]:
    print(f"DART 사업보고서 재무제표 조회 중: corp_code={corp_code}, year={year}, fs_div={fs_div}", file=sys.stderr)
    payload = request_json(
        "fnlttSinglAcntAll",
        {
            "crtfc_key": api_key,
            "corp_code": corp_code,
            "bsns_year": year,
            "reprt_code": REPORT_ANNUAL,
            "fs_div": fs_div,
        },
    )
    return payload.get("list", [])


def calculate_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    income_statements = ("IS", "CIS")
    current_assets = pick_account(rows, "BS", {"ifrs-full_CurrentAssets"}, {"유동자산"})
    current_liabilities = pick_account(rows, "BS", {"ifrs-full_CurrentLiabilities"}, {"유동부채"})
    total_assets = pick_account(rows, "BS", {"ifrs-full_Assets"}, {"자산총계"})
    total_liabilities = pick_account(rows, "BS", {"ifrs-full_Liabilities"}, {"부채총계"})
    total_equity = pick_account(rows, "BS", {"ifrs-full_Equity"}, {"자본총계"})
    cash_and_cash_equivalents = pick_account(
        rows,
        "BS",
        {"ifrs-full_CashAndCashEquivalents"},
        {"현금및현금성자산", "현금 및 현금성자산"},
    )
    revenue = pick_account(
        rows,
        income_statements,
        {"ifrs-full_Revenue", "ifrs-full_SalesRevenue"},
        {"매출액", "수익(매출액)", "영업수익"},
    )
    cost_of_sales = pick_account(
        rows,
        income_statements,
        {"ifrs-full_CostOfSales"},
        {"매출원가", "영업비용"},
    )
    gross_profit = pick_account(
        rows,
        income_statements,
        {"ifrs-full_GrossProfit"},
        {"매출총이익", "매출총이익(손실)"},
    )
    selling_general_admin_expenses = pick_account(
        rows,
        income_statements,
        {"ifrs-full_SellingGeneralAdministrativeExpenses", "ifrs-full_SellingGeneralAndAdministrativeExpense"},
        {"판매비와관리비", "판매비와 관리비", "판매관리비"},
    )
    operating_income = pick_account(
        rows,
        income_statements,
        {"ifrs-full_ProfitLossFromOperatingActivities"},
        {"영업이익", "영업이익(손실)"},
    )
    profit_before_tax = pick_account(
        rows,
        income_statements,
        {"ifrs-full_ProfitLossBeforeTax"},
        {"법인세차감전순이익", "법인세비용차감전순이익", "법인세비용차감전순이익(손실)"},
    )
    net_income = pick_account(
        rows,
        income_statements,
        {"ifrs-full_ProfitLoss"},
        {"당기순이익", "당기순이익(손실)"},
    )
    income_tax_expense = pick_account(
        rows,
        income_statements,
        {"ifrs-full_IncomeTaxExpenseContinuingOperations", "ifrs-full_IncomeTaxExpense"},
        {"법인세비용", "법인세비용(수익)"},
    )
    basic_eps = pick_account(
        rows,
        income_statements,
        {"ifrs-full_BasicEarningsLossPerShare"},
        {"기본주당이익", "기본주당이익(손실)"},
    )
    operating_cash_flow = pick_account(
        rows,
        "CF",
        {"ifrs-full_CashFlowsFromUsedInOperatingActivities"},
        {"영업활동현금흐름", "영업활동으로 인한 현금흐름"},
    )

    return {
        "revenue": amount_to_number(revenue),
        "cost_of_sales": amount_to_number(cost_of_sales),
        "gross_profit": amount_to_number(gross_profit),
        "selling_general_admin_expenses": amount_to_number(selling_general_admin_expenses),
        "operating_income": amount_to_number(operating_income),
        "profit_before_tax": amount_to_number(profit_before_tax),
        "net_income": amount_to_number(net_income),
        "income_tax_expense": amount_to_number(income_tax_expense),
        "basic_eps": amount_to_number(basic_eps),
        "operating_cash_flow": amount_to_number(operating_cash_flow),
        "cash_and_cash_equivalents": amount_to_number(cash_and_cash_equivalents),
        "current_assets": amount_to_number(current_assets),
        "current_liabilities": amount_to_number(current_liabilities),
        "total_assets": amount_to_number(total_assets),
        "total_liabilities": amount_to_number(total_liabilities),
        "total_equity": amount_to_number(total_equity),
        "gross_margin_pct": amount_to_number(safe_ratio(gross_profit, revenue)),
        "cost_of_sales_ratio_pct": amount_to_number(safe_ratio(cost_of_sales, revenue)),
        "sga_ratio_pct": amount_to_number(safe_ratio(selling_general_admin_expenses, revenue)),
        "operating_margin_pct": amount_to_number(safe_ratio(operating_income, revenue)),
        "net_margin_pct": amount_to_number(safe_ratio(net_income, revenue)),
        "debt_ratio_pct": amount_to_number(safe_ratio(total_liabilities, total_equity)),
        "current_ratio_pct": amount_to_number(safe_ratio(current_assets, current_liabilities)),
        "roe_pct": amount_to_number(safe_ratio(net_income, total_equity)),
        "roa_pct": amount_to_number(safe_ratio(net_income, total_assets)),
    }


def get_dart_indicators(api_key: str, corp_code: str, year: str) -> list[dict[str, Any]]:
    indicators: list[dict[str, Any]] = []
    for idx_cl_code in ("M210000", "M220000", "M230000", "M240000"):
        try:
            payload = request_json(
                "fnlttSinglIndx",
                {
                    "crtfc_key": api_key,
                    "corp_code": corp_code,
                    "bsns_year": year,
                    "reprt_code": REPORT_ANNUAL,
                    "idx_cl_code": idx_cl_code,
                },
            )
        except RuntimeError as exc:
            if "013" in str(exc):
                continue
            raise
        indicators.extend(payload.get("list", []))
    return indicators


def build_report_result(
    api_key: str,
    company: str,
    year: str,
    fs_div: str = "CFS",
    refresh_corp_codes: bool = False,
    include_dart_indicators: bool = False,
    corp: Corp | None = None,
) -> dict[str, Any]:
    if corp is None:
        if company.isdigit() and len(company) == 8:
            corp = Corp(company, company, "", "")
        else:
            corp = resolve_corp(api_key, company, refresh=refresh_corp_codes)

    actual_fs_div = fs_div
    try:
        rows = get_financial_rows(api_key, corp.corp_code, year, actual_fs_div)
    except RuntimeError as exc:
        if fs_div == "CFS" and "013" in str(exc):
            actual_fs_div = "OFS"
            rows = get_financial_rows(api_key, corp.corp_code, year, actual_fs_div)
        else:
            raise

    result: dict[str, Any] = {
        "company": {
            "corp_name": corp.corp_name,
            "corp_code": corp.corp_code,
            "stock_code": corp.stock_code,
        },
        "year": year,
        "report_code": REPORT_ANNUAL,
        "fs_div": actual_fs_div,
        "requested_fs_div": fs_div,
        "metrics": calculate_metrics(rows),
    }

    if include_dart_indicators:
        result["dart_indicators"] = [
            {
                "category": row.get("idx_cl_nm"),
                "name": row.get("idx_nm"),
                "value": row.get("idx_val"),
            }
            for row in get_dart_indicators(api_key, corp.corp_code, year)
        ]

    return result


def normalize_years(years: list[str] | tuple[str, ...]) -> list[str]:
    cleaned: list[str] = []
    for year in years:
        value = year.strip()
        if not value:
            continue
        if not (value.isdigit() and len(value) == 4):
            raise RuntimeError("사업연도는 4자리 숫자로 입력하세요. 예: 2022 2023 2024")
        if value not in cleaned:
            cleaned.append(value)
    if not cleaned:
        raise RuntimeError("사업연도를 하나 이상 입력하세요.")
    return cleaned


def build_comparison_result(
    api_key: str,
    company: str,
    years: list[str] | tuple[str, ...],
    fs_div: str = "CFS",
    refresh_corp_codes: bool = False,
) -> dict[str, Any]:
    normalized_years = normalize_years(years)
    if company.isdigit() and len(company) == 8:
        corp = Corp(company, company, "", "")
    else:
        corp = resolve_corp(api_key, company, refresh=refresh_corp_codes)

    reports = [
        build_report_result(
            api_key=api_key,
            company=company,
            year=year,
            fs_div=fs_div,
            corp=corp,
        )
        for year in normalized_years
    ]
    return {
        "company": reports[0]["company"],
        "years": normalized_years,
        "fs_div": fs_div,
        "reports": reports,
    }


def find_annual_report_receipt(api_key: str, corp_code: str, year: str) -> dict[str, Any]:
    payload = request_json(
        "list",
        {
            "crtfc_key": api_key,
            "corp_code": corp_code,
            "bgn_de": f"{year}0101",
            "end_de": f"{int(year) + 1}1231",
            "last_reprt_at": "Y",
            "pblntf_ty": "A",
            "pblntf_detail_ty": "A001",
            "page_count": "100",
        },
    )
    filings = payload.get("list", [])
    annuals = [row for row in filings if "사업보고서" in str(row.get("report_nm", ""))]
    if not annuals:
        raise RuntimeError(f"{year}년 사업보고서 접수번호를 찾지 못했습니다.")
    return sorted(annuals, key=lambda row: str(row.get("rcept_dt", "")), reverse=True)[0]


def download_report_document_text(api_key: str, rcept_no: str) -> str:
    blob = request_binary("document.xml", {"crtfc_key": api_key, "rcept_no": rcept_no})
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        xml_name = archive.namelist()[0]
        raw = archive.read(xml_name)
    decoded = raw.decode("utf-8", errors="ignore")
    decoded = re.sub(r"<[^>]+>", " ", decoded)
    decoded = html.unescape(decoded)
    decoded = re.sub(r"\s+", " ", decoded)
    return decoded.strip()


def extract_text_sections(text: str, limit: int = 1200) -> dict[str, str]:
    section_titles = {
        "company_overview": "회사의 개요",
        "business_overview": "사업의 내용",
        "business_summary": "사업의 개요",
        "products_services": "주요 제품 및 서비스",
        "sales_orders": "매출 및 수주상황",
        "research_development": "연구개발활동",
        "risk_management": "위험관리",
        "future_strategy": "향후 추진하려는 신규사업",
        "management_discussion": "이사의 경영진단 및 분석의견",
    }
    markers = list(section_titles.values()) + [
        "재무에 관한 사항",
        "이사의 경영진단",
        "임원 및 직원",
        "계열회사",
        "주주에 관한 사항",
        "감사인의 감사의견",
    ]
    found: dict[str, str] = {}
    for key, title in section_titles.items():
        match = re.search(re.escape(title), text)
        if not match:
            continue
        start = match.start()
        end_candidates = [
            other.start()
            for marker in markers
            if marker != title
            for other in [re.search(re.escape(marker), text[start + len(title):])]
            if other
        ]
        end = start + len(title) + min(end_candidates) if end_candidates else min(len(text), start + limit * 2)
        snippet = text[start:end].strip()
        found[key] = snippet[:limit].strip()
    return found


def build_report_text_result(api_key: str, company: str, year: str, limit: int = 1200) -> dict[str, Any]:
    corp = Corp(company, company, "", "") if company.isdigit() and len(company) == 8 else resolve_corp(api_key, company)
    filing = find_annual_report_receipt(api_key, corp.corp_code, year)
    full_text = download_report_document_text(api_key, str(filing["rcept_no"]))
    return {
        "company": {"corp_name": corp.corp_name, "corp_code": corp.corp_code, "stock_code": corp.stock_code},
        "year": year,
        "filing": filing,
        "sections": extract_text_sections(full_text, limit=limit),
    }


def require_api_key(api_key: str | None = None) -> str:
    resolved = api_key or os.getenv("DART_API_KEY")
    if not resolved:
        raise RuntimeError("DART API 키가 필요합니다. DART_API_KEY 환경변수를 설정하세요.")
    return resolved


def write_csv(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    metrics = result["metrics"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", "label", "value", "unit"])
        for key, value in metrics.items():
            unit = "원" if key in AMOUNT_METRICS or key in PER_SHARE_METRICS else "%"
            writer.writerow([key, METRIC_LABELS.get(key, key), value, unit])


def normalize_amount_unit(amount_unit: str = "eok") -> str:
    normalized = UNIT_ALIASES.get(amount_unit.strip().lower()) or UNIT_ALIASES.get(amount_unit.strip())
    if not normalized:
        available = ", ".join(unit["label"] for unit in AMOUNT_UNITS.values())
        raise RuntimeError(f"지원하지 않는 단위입니다: {amount_unit}. 사용 가능 단위: {available}")
    return normalized


def amount_unit_label(amount_unit: str = "eok") -> str:
    return str(AMOUNT_UNITS[normalize_amount_unit(amount_unit)]["label"])


def format_amount_won(value: int | float | None, amount_unit: str = "eok") -> str:
    if value is None:
        return "-"
    unit_key = normalize_amount_unit(amount_unit)
    unit = AMOUNT_UNITS[unit_key]
    scaled = value / int(unit["divisor"])
    if unit_key == "trillion":
        formatted = f"{scaled:,.1f}"
    elif abs(scaled) >= 100:
        formatted = f"{scaled:,.0f}"
    elif abs(scaled) >= 10:
        formatted = f"{scaled:,.1f}"
    else:
        formatted = f"{scaled:,.2f}"
    return f"{formatted} {unit['label']}"


def format_ratio(value: int | float | None) -> str:
    if value is None:
        return "-"
    return f"{value:,.2f}%"


def format_per_share(value: int | float | None) -> str:
    if value is None:
        return "-"
    return f"{value:,.0f} 원"


def format_metric_value(key: str, value: int | float | None, amount_unit: str = "eok") -> str:
    if key in AMOUNT_METRICS:
        return format_amount_won(value, amount_unit)
    if key in PER_SHARE_METRICS:
        return format_per_share(value)
    return format_ratio(value)


def display_metric_rows(
    result: dict[str, Any],
    keys: tuple[str, ...] = DISPLAY_METRICS,
    amount_unit: str = "eok",
) -> list[dict[str, Any]]:
    rows = []
    metrics = result["metrics"]
    for key in keys:
        value = metrics.get(key)
        rows.append(
            {
                "key": key,
                "label": METRIC_LABELS.get(key, key),
                "value": value,
                "formatted": format_metric_value(key, value, amount_unit),
            }
        )
    return rows


def format_result_message(result: dict[str, Any], amount_unit: str = "eok") -> str:
    company = result["company"]
    lines = [f"{company['corp_name']} {result['year']}년 주요 재무지표 ({result['fs_div']}, 단위 {amount_unit_label(amount_unit)})"]
    for row in display_metric_rows(result, amount_unit=amount_unit):
        lines.append(f"{row['label']}: {row['formatted']}")
    return "\n".join(lines)


def format_comparison_message(comparison: dict[str, Any], amount_unit: str = "eok") -> str:
    company = comparison["company"]
    reports = comparison["reports"]
    lines = [f"{company['corp_name']} 연도별 주요 재무지표 ({comparison['fs_div']}, 단위 {amount_unit_label(amount_unit)})"]
    for key in DISPLAY_METRICS:
        label = METRIC_LABELS.get(key, key)
        values = []
        for report in reports:
            values.append(f"{report['year']}: {format_metric_value(key, report['metrics'].get(key), amount_unit)}")
        lines.append(f"{label} | " + " / ".join(values))
    return "\n".join(lines)


def print_table(result: dict[str, Any], amount_unit: str = "eok") -> None:
    company = result["company"]
    title = f"{company['corp_name']} {result['year']}년 사업보고서 주요 재무지표 ({result['fs_div']})"
    print(title)
    print("=" * len(title))
    print(f"{'구분':<18} {'값':>18}")
    print("-" * 40)
    for key, value in result["metrics"].items():
        label = METRIC_LABELS.get(key, key)
        formatted = format_metric_value(key, value, amount_unit)
        print(f"{label:<18} {formatted:>18}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="DART 사업보고서에서 특정 기업/연도 재무 지표를 추출합니다."
    )
    parser.add_argument("company", help="기업명, 종목코드, 또는 DART corp_code")
    parser.add_argument("year", help="사업연도 예: 2024")
    parser.add_argument("--api-key", default=os.getenv("DART_API_KEY"), help="DART API key. 기본값: DART_API_KEY")
    parser.add_argument("--fs-div", choices=("CFS", "OFS"), default="CFS", help="CFS 연결, OFS 별도")
    parser.add_argument("--refresh-corp-codes", action="store_true", help="DART 기업코드 캐시 갱신")
    parser.add_argument("--csv", type=Path, help="계산 지표를 CSV로 저장")
    parser.add_argument("--format", choices=("table", "json"), default="table", help="출력 형식")
    parser.add_argument("--unit", choices=tuple(AMOUNT_UNITS), default="eok", help="금액 표시 단위")
    parser.add_argument("--include-dart-indicators", action="store_true", help="2022년 이후 DART 주요지표도 함께 조회")
    parser.add_argument("--include-text", action="store_true", help="사업보고서 원문에서 주요 텍스트 섹션도 조회")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        api_key = require_api_key(args.api_key)
        result = build_report_result(
            api_key=api_key,
            company=args.company,
            year=args.year,
            fs_div=args.fs_div,
            refresh_corp_codes=args.refresh_corp_codes,
            include_dart_indicators=args.include_dart_indicators,
        )
        if args.include_text:
            result["text_sections"] = build_report_text_result(api_key, args.company, args.year)["sections"]
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.csv:
        write_csv(args.csv, result)

    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_table(result, amount_unit=args.unit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
