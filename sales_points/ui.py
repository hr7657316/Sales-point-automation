"""A tiny local web UI for the point engine: upload a Fit Report, click Run.

Standard library only (no extra installs). Start with
``python3 -m sales_points.ui`` and a browser tab opens at
http://localhost:8765. Nothing leaves the laptop.
"""

from __future__ import annotations

import html
import tempfile
import threading
import webbrowser
from email import message_from_bytes
from email.policy import HTTP
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

from .cli import _load_csv
from .comp import load_comp_plans
from .engine import PointEngine
from .fit_report import load_fit_report_workbook
from .report import write_master_sheet, write_rep_sheets, write_review_queue, write_summary
from .rules import RuleBook
from .workbook import REP_NAMES, build_workbook

PORT = 8765
STATE: dict = {"out_dir": None, "result": None}

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>Match One Point Engine</title>
<style>
 body{font-family:-apple-system,Segoe UI,Arial,sans-serif;background:#f6f7f9;margin:0;color:#1d2433}
 .wrap{max-width:980px;margin:40px auto;padding:0 24px}
 .card{background:#fff;border:1px solid #e3e6ea;border-radius:12px;padding:28px 32px;margin-bottom:24px;box-shadow:0 1px 2px rgba(0,0,0,.04)}
 h1{margin:0 0 6px;font-size:26px} .sub{color:#5b6472;margin:0 0 22px}
 label{display:block;font-weight:600;margin:14px 0 6px}
 input[type=text]{padding:10px 12px;border:1px solid #cfd4da;border-radius:8px;font-size:15px;width:260px}
 input[type=file]{font-size:15px}
 button{background:#1f5eff;color:#fff;border:0;border-radius:8px;padding:12px 22px;font-size:16px;font-weight:600;cursor:pointer;margin-top:18px}
 button:hover{background:#174ad0}
 table{border-collapse:collapse;width:100%%;font-size:15px} th,td{padding:9px 12px;border-bottom:1px solid #eceff2;text-align:left}
 th{background:#f0f3f7;font-weight:600} td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
 .stat{display:inline-block;background:#eef3ff;border-radius:10px;padding:14px 20px;margin:0 12px 12px 0;min-width:150px}
 .stat b{display:block;font-size:28px} .stat span{color:#5b6472;font-size:13px}
 .dl a{display:inline-block;margin:6px 10px 0 0;padding:9px 14px;border:1px solid #1f5eff;border-radius:8px;color:#1f5eff;text-decoration:none;font-weight:600}
 .flag{background:#fff6e5;border-left:4px solid #f5a623;padding:12px 16px;border-radius:6px;margin-top:8px}
 .muted{color:#5b6472;font-size:13px}
 .spin{display:none;margin-left:12px;color:#5b6472}
</style></head><body><div class="wrap">
<div class="card">
 <h1>Match One Point Engine</h1>
 <p class="sub">Upload the Monthly Fit Report. The engine scores every row against Allissa's rules and builds the rep point sheets.</p>
 <form method="post" action="/run" enctype="multipart/form-data" onsubmit="document.getElementById('s').style.display='inline'">
  <label>Fit Report (.xlsx or .csv)</label><input type="file" name="report" required accept=".xlsx,.xlsm,.csv">
  <label>Month label</label><input type="text" name="month" value="%(month)s">
  <br><button type="submit">Run the engine</button><span id="s" class="spin">Scoring...</span>
 </form>
</div>
%(results)s
<p class="muted">Runs entirely on this computer. Rules: rules/point_rules.csv and friends. Nothing is written to Google Drive.</p>
</div></body></html>"""


def _score(path: Path, month: str) -> dict:
    if path.suffix.lower() in {".xlsx", ".xlsm"}:
        rows = load_fit_report_workbook(path)
    else:
        rows = _load_csv(path)
    engine = PointEngine(rulebook=RuleBook.load(Path("rules")))
    results, summaries = engine.run(rows)
    out_dir = Path(tempfile.mkdtemp(prefix="points_"))
    write_master_sheet(out_dir, results)
    write_rep_sheets(out_dir, summaries)
    write_summary(out_dir, summaries)
    write_review_queue(out_dir, results)
    label = month or path.stem.upper()
    wb_path = build_workbook(results, label,
                             out_dir / f"{label.replace(' ', '_')}_Point_Sheets_ENGINE.xlsx")
    plans = load_comp_plans("rules/comp_plans.csv")
    reps = []
    for key, s in summaries.items():
        pts = s.total_points if hasattr(s, "total_points") else s.row_points
        name, plan_key = REP_NAMES.get(key, (key, None))
        dollars = plans[plan_key].commission_for(pts) if plan_key in plans else None
        gold = sum(1 for res, rep, p in s.rows if any("GOLD" in b for b in res.bonuses_applied))
        reps.append((name, key, pts, gold, dollars))
    reps.sort(key=lambda r: -r[2])
    flagged = [(r.row.rep, r.row.patient, r.row.product, r.row.type, r.explanation)
               for r in results if r.review_needed]
    STATE.update(out_dir=out_dir, result={
        "rows": len(results), "reps": reps, "flagged": flagged,
        "workbook": wb_path.name, "month": label})
    return STATE["result"]


def _render_results(res: dict | None) -> str:
    if not res:
        return ""
    stats = (f'<div class="stat"><b>{res["rows"]}</b><span>rows scored</span></div>'
             f'<div class="stat"><b>{len(res["reps"])}</b><span>reps</span></div>'
             f'<div class="stat"><b>{len(res["flagged"])}</b><span>rows needing a human</span></div>')
    body = "".join(
        f"<tr><td>{html.escape(n)}</td><td class='muted'>{html.escape(k)}</td>"
        f"<td class='num'>{p:,}</td><td class='num'>{g}</td>"
        f"<td class='num'>{('$' + format(d, ',')) if d is not None else '-'}</td></tr>"
        for n, k, p, g, d in res["reps"])
    table = ("<table><tr><th>Rep</th><th>Code</th><th class='num'>Points</th>"
             "<th class='num'>Gold pairs</th><th class='num'>Commission</th></tr>" + body + "</table>")
    flags = "".join(
        f"<div class='flag'><b>{html.escape(pat)}</b> - {html.escape(rep)}<br>"
        f"{html.escape(prod)} | {html.escape(typ)}<br><span class='muted'>{html.escape(why)}</span></div>"
        for rep, pat, prod, typ, why in res["flagged"]) or "<p class='muted'>None.</p>"
    dl = (f'<div class="dl"><a href="/download/{res["workbook"]}">Download point sheet workbook (.xlsx)</a>'
          f'<a href="/download/master_point_sheet.csv">All rows with reasoning (.csv)</a>'
          f'<a href="/download/review_queue.csv">Review queue (.csv)</a></div>')
    return (f'<div class="card"><h1>{html.escape(res["month"])}</h1>{stats}{dl}</div>'
            f'<div class="card"><h2>Points by rep</h2>{table}'
            f'<p class="muted">Base points before honorarium and new-customer bonuses. '
            f'Commission shown where the rep\'s comp table is loaded.</p></div>'
            f'<div class="card"><h2>Rows needing a human decision</h2>{flags}</div>')


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # quiet
        pass

    def _send(self, body: bytes, ctype="text/html; charset=utf-8", extra=None):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/download/") and STATE["out_dir"]:
            name = unquote(self.path[len("/download/"):])
            f = Path(STATE["out_dir"]) / name
            if f.is_file():
                self._send(f.read_bytes(), "application/octet-stream",
                           {"Content-Disposition": f'attachment; filename="{f.name}"'})
                return
        page = PAGE % {"month": html.escape((STATE["result"] or {}).get("month", "AUGUST 2026")),
                       "results": _render_results(STATE["result"])}
        self._send(page.encode())

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        msg = message_from_bytes(
            b"Content-Type: " + self.headers["Content-Type"].encode() + b"\r\n\r\n" + raw, policy=HTTP)
        month, upload, fname = "", None, "report.csv"
        for part in msg.iter_parts():
            if part.get_param("name", header="content-disposition") == "month":
                month = part.get_content().strip()
            elif part.get_param("name", header="content-disposition") == "report":
                fname = part.get_filename() or fname
                upload = part.get_payload(decode=True)
        if not upload:
            self._send(b"No file received. <a href='/'>Back</a>")
            return
        tmp = Path(tempfile.mkdtemp(prefix="fitreport_")) / fname
        tmp.write_bytes(upload)
        try:
            _score(tmp, month)
        except Exception as exc:  # show the error on the page instead of dying
            self._send(f"<pre>Could not score this file:\n{html.escape(str(exc))}</pre>"
                       f"<a href='/'>Back</a>".encode())
            return
        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()


def main() -> int:
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://localhost:{PORT}"
    print(f"Point engine UI running at {url}  (Ctrl+C to stop)")
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
