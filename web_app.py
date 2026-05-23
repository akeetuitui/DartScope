from __future__ import annotations

import re
from html import escape

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse

from dart_financials import (
    AMOUNT_UNITS,
    DISPLAY_METRICS,
    METRIC_LABELS,
    build_comparison_result,
    display_metric_rows,
    amount_unit_label,
    format_metric_value,
    require_api_key,
)

app = FastAPI(title="DartScope")


def parse_years_input(years: str) -> list[str]:
    return [part for part in re.split(r"[\s,]+", years.strip()) if part]


def page(content: str) -> str:
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DartScope</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f8fa;
      --surface: #ffffff;
      --ink: #191f28;
      --muted: #8b95a1;
      --line: #eef0f3;
      --blue: #3182f6;
      --blue-soft: #e8f3ff;
      --red: #f04452;
      --green: #00a661;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: var(--ink); background: var(--bg); }}
    header {{ position: sticky; top: 0; z-index: 10; background: rgba(255,255,255,.9); backdrop-filter: blur(18px); border-bottom: 1px solid var(--line); }}
    nav {{ max-width: 1080px; margin: 0 auto; height: 58px; display: flex; align-items: center; justify-content: space-between; padding: 0 22px; }}
    .brand {{ font-size: 19px; font-weight: 900; letter-spacing: 0; }}
    .navlinks {{ display: flex; gap: 22px; color: #4e5968; font-size: 14px; font-weight: 700; }}
    main {{ max-width: 1080px; margin: 0 auto; padding: 44px 22px 72px; }}
    .hero {{ display: grid; grid-template-columns: minmax(0, 1fr) 360px; gap: 28px; align-items: end; margin-bottom: 26px; }}
    h1 {{ margin: 0; max-width: 760px; font-size: 46px; line-height: 1.12; letter-spacing: 0; }}
    .sub {{ margin: 14px 0 0; color: var(--muted); font-size: 17px; line-height: 1.55; }}
    .search-card {{ background: var(--surface); border: 1px solid var(--line); border-radius: 18px; padding: 18px; box-shadow: 0 12px 30px rgba(25,31,40,.06); }}
    form {{ display: grid; gap: 12px; }}
    label {{ display: grid; gap: 8px; color: #4e5968; font-size: 13px; font-weight: 800; }}
    input, select {{ width: 100%; height: 48px; border: 1px solid #e5e8eb; border-radius: 12px; padding: 0 14px; font: inherit; background: #fff; color: var(--ink); outline: none; }}
    input:focus, select:focus {{ border-color: var(--blue); box-shadow: 0 0 0 3px var(--blue-soft); }}
    button {{ height: 50px; border: 0; border-radius: 12px; padding: 0 18px; font-size: 16px; font-weight: 900; color: white; background: var(--blue); cursor: pointer; }}
    button:hover {{ background: #1b64da; }}
    .hint {{ margin: 10px 2px 0; color: var(--muted); font-size: 13px; }}
    .panel {{ background: var(--surface); border: 1px solid var(--line); border-radius: 18px; padding: 22px; box-shadow: 0 12px 30px rgba(25,31,40,.05); }}
    .notice, .error {{ margin-top: 20px; border-radius: 16px; padding: 16px 18px; font-weight: 700; }}
    .notice {{ color: #4e5968; background: #fff; border: 1px solid var(--line); }}
    .error {{ color: var(--red); background: #fff5f6; border: 1px solid #ffe1e4; }}
    .result-head {{ display: flex; justify-content: space-between; gap: 18px; align-items: flex-end; margin-bottom: 18px; }}
    .result-title {{ font-size: 24px; font-weight: 900; }}
    .result-meta {{ color: var(--muted); font-size: 14px; font-weight: 700; }}
    .cards {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 18px; }}
    .metric-card {{ background: #f9fafb; border: 1px solid var(--line); border-radius: 16px; padding: 16px; }}
    .metric-card .label {{ color: var(--muted); font-size: 13px; font-weight: 800; }}
    .metric-card .value {{ margin-top: 8px; font-size: 23px; line-height: 1.18; font-weight: 950; letter-spacing: 0; }}
    .table-wrap {{ overflow-x: auto; border: 1px solid var(--line); border-radius: 16px; }}
    table {{ width: 100%; min-width: 620px; border-collapse: collapse; background: white; }}
    th, td {{ padding: 16px 18px; border-bottom: 1px solid var(--line); text-align: right; white-space: nowrap; }}
    th:first-child, td:first-child {{ text-align: left; position: sticky; left: 0; background: white; font-weight: 900; }}
    th {{ color: var(--muted); font-size: 13px; font-weight: 900; background: #fbfcfd; }}
    th:first-child {{ background: #fbfcfd; }}
    td {{ font-size: 15px; font-weight: 750; font-variant-numeric: tabular-nums; }}
    tr:last-child td {{ border-bottom: 0; }}
    @media (max-width: 860px) {{ .hero {{ grid-template-columns: 1fr; }} h1 {{ font-size: 34px; }} .cards {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} .navlinks {{ display: none; }} }}
    @media (max-width: 520px) {{ main {{ padding: 32px 16px 56px; }} .cards {{ grid-template-columns: 1fr; }} .result-head {{ display: block; }} }}
  </style>
</head>
<body>
  <header>
    <nav>
      <div class="brand">DartScope</div>
      <div class="navlinks"><span>재무지표</span><span>연도 비교</span><span>DART</span></div>
    </nav>
  </header>
  <main>{content}</main>
</body>
</html>"""


def form_html(
    company: str = "삼성전자",
    years: str = "2022 2023 2024",
    fs_div: str = "CFS",
    amount_unit: str = "eok",
) -> str:
    cfs_selected = "selected" if fs_div == "CFS" else ""
    ofs_selected = "selected" if fs_div == "OFS" else ""
    unit_options = "".join(
        f"<option value=\"{escape(key)}\" {'selected' if key == amount_unit else ''}>{escape(str(info['label']))}</option>"
        for key, info in AMOUNT_UNITS.items()
    )
    return f"""
<section class="hero">
  <div>
    <h1>사업보고서 숫자를<br>한눈에 비교하세요</h1>
    <p class="sub">기업명과 여러 사업연도를 입력하면 DART 사업보고서에서 매출액, 영업이익, 영업이익률, ROE를 바로 비교합니다.</p>
  </div>
  <div class="search-card">
    <form method="post" action="/report">
      <label>기업명 또는 종목코드
        <input name="company" value="{escape(company)}" placeholder="삼성전자" required>
      </label>
      <label>사업연도
        <input name="years" value="{escape(years)}" placeholder="2022 2023 2024" required>
      </label>
      <label>재무제표
        <select name="fs_div">
          <option value="CFS" {cfs_selected}>연결</option>
          <option value="OFS" {ofs_selected}>별도</option>
        </select>
      </label>
      <label>금액 단위
        <select name="amount_unit">
          {unit_options}
        </select>
      </label>
      <button type="submit">비교하기</button>
    </form>
    <div class="hint">연도는 공백이나 쉼표로 구분하세요. 단위는 원, 천원, 백만원, 억원, 조원 중 선택할 수 있습니다.</div>
  </div>
</section>"""


def render_result(comparison: dict[str, object], amount_unit: str = "eok") -> str:
    reports = comparison["reports"]
    latest = reports[-1]
    corp = comparison["company"]
    cards = "".join(
        f"<div class='metric-card'><div class='label'>{escape(row['label'])}</div><div class='value'>{escape(row['formatted'])}</div></div>"
        for row in display_metric_rows(latest, amount_unit=amount_unit)[:4]
    )
    header_cells = "".join(f"<th>{escape(report['year'])}</th>" for report in reports)
    body_rows = "".join(
        "<tr>"
        f"<td>{escape(METRIC_LABELS.get(key, key))}</td>"
        + "".join(f"<td>{escape(format_metric_value(key, report['metrics'].get(key), amount_unit))}</td>" for report in reports)
        + "</tr>"
        for key in DISPLAY_METRICS
    )
    return f"""
<section class="panel">
  <div class="result-head">
    <div>
      <div class="result-title">{escape(corp['corp_name'])}</div>
      <div class="result-meta">{escape(', '.join(comparison['years']))}년 / {escape(comparison['fs_div'])} / 단위 {escape(amount_unit_label(amount_unit))}</div>
    </div>
  </div>
  <div class="cards">{cards}</div>
  <div class="table-wrap">
    <table>
      <thead><tr><th>지표</th>{header_cells}</tr></thead>
      <tbody>{body_rows}</tbody>
    </table>
  </div>
</section>"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return page(form_html() + '<div class="notice">DART_API_KEY 환경변수를 설정한 뒤 조회할 수 있습니다.</div>')


@app.post("/report", response_class=HTMLResponse)
def report(
    request: Request,
    company: str = Form(...),
    years: str = Form(...),
    fs_div: str = Form("CFS"),
    amount_unit: str = Form("eok"),
) -> str:
    del request
    form = form_html(company=company, years=years, fs_div=fs_div, amount_unit=amount_unit)
    try:
        comparison = build_comparison_result(require_api_key(), company.strip(), parse_years_input(years), fs_div)
    except Exception as exc:
        return page(form + f'<div class="error">{escape(str(exc))}</div>')
    return page(form + render_result(comparison, amount_unit=amount_unit))
