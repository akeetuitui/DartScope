from __future__ import annotations

from html import escape

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse

from dart_financials import build_report_result, display_metric_rows, require_api_key

app = FastAPI(title="DartScope")


def page(content: str) -> str:
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DartScope</title>
  <style>
    :root {{ color-scheme: light; --ink:#17202a; --muted:#667085; --line:#d9dee7; --accent:#0f766e; --soft:#f4f7f9; --danger:#b42318; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: var(--ink); background: #fbfcfd; }}
    main {{ max-width: 880px; margin: 0 auto; padding: 48px 20px; }}
    h1 {{ margin: 0 0 10px; font-size: 34px; line-height: 1.15; }}
    p {{ margin: 0; color: var(--muted); }}
    form {{ display: grid; grid-template-columns: 1fr 140px 140px auto; gap: 10px; align-items: end; margin: 28px 0; padding: 18px; border: 1px solid var(--line); border-radius: 8px; background: white; }}
    label {{ display: grid; gap: 7px; font-size: 13px; font-weight: 700; }}
    input, select {{ width: 100%; height: 42px; border: 1px solid var(--line); border-radius: 6px; padding: 0 12px; font: inherit; background: white; }}
    button {{ height: 42px; border: 0; border-radius: 6px; padding: 0 18px; font-weight: 800; color: white; background: var(--accent); cursor: pointer; }}
    table {{ width: 100%; border-collapse: collapse; overflow: hidden; border: 1px solid var(--line); border-radius: 8px; background: white; }}
    th, td {{ padding: 13px 16px; border-bottom: 1px solid var(--line); text-align: left; }}
    th {{ background: var(--soft); font-size: 13px; }}
    td:last-child {{ text-align: right; font-variant-numeric: tabular-nums; }}
    tr:last-child td {{ border-bottom: 0; }}
    .notice {{ margin-top: 14px; padding: 13px 16px; border-radius: 8px; background: #fff7ed; color: #9a3412; }}
    .error {{ margin-top: 14px; padding: 13px 16px; border-radius: 8px; background: #fef3f2; color: var(--danger); }}
    .meta {{ margin: -14px 0 18px; color: var(--muted); }}
    @media (max-width: 720px) {{ form {{ grid-template-columns: 1fr; }} button {{ width: 100%; }} }}
  </style>
</head>
<body>
  <main>
    <h1>DartScope</h1>
    <p>DART 사업보고서에서 주요 재무지표를 추출합니다.</p>
    {content}
  </main>
</body>
</html>"""


def form_html(company: str = "삼성전자", year: str = "2024", fs_div: str = "CFS") -> str:
    cfs_selected = "selected" if fs_div == "CFS" else ""
    ofs_selected = "selected" if fs_div == "OFS" else ""
    return f"""
<form method="post" action="/report">
  <label>기업명 또는 종목코드
    <input name="company" value="{escape(company)}" placeholder="삼성전자" required>
  </label>
  <label>사업연도
    <input name="year" value="{escape(year)}" pattern="[0-9]{{4}}" placeholder="2024" required>
  </label>
  <label>재무제표
    <select name="fs_div">
      <option value="CFS" {cfs_selected}>연결</option>
      <option value="OFS" {ofs_selected}>별도</option>
    </select>
  </label>
  <button type="submit">조회</button>
</form>"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return page(form_html() + '<div class="notice">DART_API_KEY 환경변수를 설정한 뒤 조회할 수 있습니다.</div>')


@app.post("/report", response_class=HTMLResponse)
def report(
    request: Request,
    company: str = Form(...),
    year: str = Form(...),
    fs_div: str = Form("CFS"),
) -> str:
    del request
    form = form_html(company=company, year=year, fs_div=fs_div)
    try:
        result = build_report_result(require_api_key(), company.strip(), year.strip(), fs_div)
    except Exception as exc:
        return page(form + f'<div class="error">{escape(str(exc))}</div>')

    corp = result["company"]
    rows = "".join(
        f"<tr><td>{escape(row['label'])}</td><td>{escape(row['formatted'])}</td></tr>"
        for row in display_metric_rows(result)
    )
    table = f"""
<div class="meta">{escape(corp['corp_name'])} / {escape(result['year'])}년 / {escape(result['fs_div'])}</div>
<table>
  <thead><tr><th>구분</th><th>값</th></tr></thead>
  <tbody>{rows}</tbody>
</table>"""
    return page(form + table)
