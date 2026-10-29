
"""Minimal dashboard for the LLM agent evaluation project."""

import json
import os
import subprocess
import sys
import threading
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
RESULTS = ROOT / "results"
HOST = "127.0.0.1"
PORT = int(os.environ.get("EVAL_DASHBOARD_PORT", "8765"))

LOCK = threading.Lock()
STATE = {
    "running": False,
    "log": [],
    "exit_code": None,
    "error": None,
}
PROCESS = None

PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Agent Lab</title>
<style>
:root {
    --bg: #111214;
    --panel: #151618;
    --border: #414247;
    --text: #eeeeF3;
    --muted: #85858f;
    --purple: #a879ff;
    --blue: #5c9eff;
    --green: #62b98b;
    --yellow: #e7bd58;
    --red: #ed7777;
}
* { box-sizing: border-box; }
body {
    margin: 0;
    background: #d4d4d4;
    color: var(--text);
    font: 13px/1.45 "Segoe UI", Arial, sans-serif;
}
button, select { font: inherit; }
button { cursor: pointer; }
button:disabled { opacity: .5; cursor: wait; }
.app {
    max-width: 1440px;
    min-height: 100vh;
    margin: auto;
    background: var(--bg);
    border: 1px solid #34353a;
}
header {
    height: 58px;
    padding: 0 22px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid #2c2d31;
    gap: 15px;
}
.brand {
    font-size: 17px;
    font-weight: 700;
    letter-spacing: -.4px;
    white-space: nowrap;
}
.brand-mark { color: var(--purple); margin-right: 8px; }
nav { display: flex; gap: 5px; align-items: center; }
nav button {
    background: transparent;
    color: var(--muted);
    border: 0;
    border-radius: 7px;
    padding: 9px 12px;
}
nav button.active {
    color: white;
    background: #7653a8;
}
select, .secondary {
    background: #17181b;
    color: var(--text);
    border: 1px solid #393a40;
    border-radius: 6px;
    padding: 8px 10px;
}
main { padding: 20px 20px 26px; }
.toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
}
.filters { display: flex; gap: 9px; flex-wrap: wrap; }
.toolbar select { min-width: 145px; }
.primary {
    color: white;
    background: #7551a9;
    border: 1px solid #8763ba;
    border-radius: 7px;
    padding: 9px 13px;
    font-weight: 600;
}
.primary:hover { background: #8861bc; }
.metrics {
    display: grid;
    grid-template-columns: repeat(3,minmax(0,1fr));
    gap: 10px;
    margin-bottom: 12px;
}
.metric, .section {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 6px;
}
.metric {
    min-height: 105px;
    padding: 14px 16px;
    position: relative;
}
.metric-label {
    color: #c3c3ca;
    font-size: 12px;
}
.metric-icon {
    position: absolute;
    right: 15px;
    top: 12px;
    color: var(--purple);
    font-size: 17px;
}
.metric-value {
    font-size: 25px;
    font-weight: 650;
    letter-spacing: -.7px;
    margin-top: 12px;
}
.metric-note {
    color: var(--muted);
    font-size: 10px;
    margin-top: 2px;
}
.section { padding: 15px; margin-bottom: 12px; }
.section-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    margin-bottom: 13px;
}
h2 {
    font-size: 15px;
    font-weight: 600;
    margin: 0;
}
.small { font-size: 10px; color: var(--muted); }
.status-row {
    display: grid;
    grid-template-columns: minmax(150px,1fr) 95px 120px;
    align-items: center;
    gap: 12px;
    padding: 13px 0;
    border-bottom: 1px solid #292a2e;
}
.status-row:last-child { border-bottom: 0; padding-bottom: 2px; }
.status-name { font-weight: 600; }
.status-detail { color: var(--muted); font-size: 10px; margin-top: 2px; }
.pill {
    display: inline-block;
    width: fit-content;
    padding: 3px 9px;
    border-radius: 4px;
    font-size: 10px;
    font-weight: 600;
    background: #303138;
    color: #c5c5cf;
}
.pill.good { background: #28523d; color: #a4e1bc; }
.pill.bad { background: #512b2e; color: #ffb2b2; }
.pill.purple { background: #38294f; color: #d4b7ff; }
.pill.warn { background: #4d4023; color: #f0d48a; }
.right { text-align: right; }
.hidden { display: none !important; }
table { width: 100%; border-collapse: collapse; }
th {
    text-align: left;
    color: var(--muted);
    font-size: 10px;
    font-weight: 500;
    padding: 10px 9px;
    border-bottom: 1px solid #37383e;
}
td {
    padding: 11px 9px;
    border-bottom: 1px solid #292a2e;
    vertical-align: top;
}
tbody tr:last-child td { border-bottom: 0; }
tbody tr:hover { background: #1c1d21; }
.table-wrap { overflow-x: auto; }
.answer {
    min-width: 250px;
    max-width: 500px;
    white-space: normal;
    color: #c4c4ce;
    overflow-wrap: anywhere;
}
.bar-row {
    display: grid;
    grid-template-columns: 150px minmax(60px,1fr) 60px;
    align-items: center;
    gap: 12px;
    margin: 18px 0;
}
.track {
    height: 8px;
    border-radius: 8px;
    background: #303137;
    overflow: hidden;
}
.fill { height: 100%; border-radius: 8px; }
.baseline { background: var(--purple); }
.tool { background: var(--blue); }
.memory { background: var(--green); }
.log {
    margin-top: 12px;
    padding: 10px;
    min-height: 55px;
    max-height: 150px;
    overflow: auto;
    background: #101114;
    border: 1px solid #303137;
    border-radius: 5px;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    color: #b9b9c5;
    font: 11px/1.5 Consolas, monospace;
}
.empty { padding: 22px; text-align: center; color: var(--muted); }
#toast {
    position: fixed;
    bottom: 20px;
    right: 20px;
    display: none;
    max-width: 340px;
    padding: 12px 15px;
    background: #292532;
    border: 1px solid #68518b;
    border-radius: 7px;
}
#toast.show { display: block; }
footer {
    display: flex;
    justify-content: space-between;
    color: #686871;
    font-size: 10px;
    padding: 5px 2px 0;
}
@media(max-width:750px) {
    header { height: auto; padding: 14px; flex-wrap: wrap; }
    nav { width: 100%; overflow-x: auto; }
    nav button { white-space: nowrap; }
    main { padding: 12px; }
    .metrics { grid-template-columns: repeat(2,minmax(0,1fr)); }
    .toolbar { align-items: flex-start; flex-direction: column; }
    .status-row { grid-template-columns: minmax(100px,1fr) 75px; }
    .status-row .right { display: none; }
    .bar-row { grid-template-columns: 110px minmax(40px,1fr) 48px; gap: 7px; }
}
@media(max-width:420px) {
    .metrics { grid-template-columns: 1fr 1fr; gap: 7px; }
    .metric { padding: 11px; }
    .metric-value { font-size: 22px; }
}
</style>
</head>
<body>
<div class="app">
<header>
    <div class="brand"><span class="brand-mark">◈</span>Agent Lab</div>
    <nav>
        <button class="active" data-tab="overview" onclick="showTab('overview')">Overview</button>
        <button data-tab="metrics" onclick="showTab('metrics')">Model Metrics</button>
        <button data-tab="tasks" onclick="showTab('tasks')">Task Results</button>
    </nav>
</header>

<main>
    <div class="toolbar">
        <div class="filters">
            <select id="reportSelect" onchange="loadReport()">
                <option value="">Select report</option>
            </select>
            <select id="conditionSelect" onchange="renderTasks()">
                <option value="baseline">Direct Context</option>
                <option value="tool">Tool Retrieval</option>
                <option value="memory">Persistent Memory</option>
            </select>
        </div>
        <button class="primary" id="runBtn" onclick="startRun()">Run Evaluation</button>
    </div>

    <section id="overview">
        <div class="metrics">
            <div class="metric">
                <div class="metric-label">Best Accuracy</div>
                <div class="metric-icon">◎</div>
                <div class="metric-value" id="bestAccuracy">—</div>
                <div class="metric-note" id="bestNote">—</div>
            </div>
            <div class="metric">
                <div class="metric-label">Average Latency</div>
                <div class="metric-icon">◷</div>
                <div class="metric-value" id="avgLatency">—</div>
                <div class="metric-note" id="latencyNote">Selected condition</div>
            </div>
            <div class="metric">
                <div class="metric-label">Average Tokens</div>
                <div class="metric-icon">▤</div>
                <div class="metric-value" id="avgTokens">—</div>
                <div class="metric-note">Per task</div>
            </div>
            <div class="metric">
                <div class="metric-label">Retrieval Success</div>
                <div class="metric-icon">⌕</div>
                <div class="metric-value" id="retrieval">—</div>
                <div class="metric-note">Retrieval-required tasks</div>
            </div>
            <div class="metric">
                <div class="metric-label">Executed Calls</div>
                <div class="metric-icon">↗</div>
                <div class="metric-value" id="executedCalls">—</div>
                <div class="metric-note">Selected condition</div>
            </div>
            <div class="metric">
                <div class="metric-label">Rejected Calls</div>
                <div class="metric-icon">⚠</div>
                <div class="metric-value" id="rejectedCalls">—</div>
                <div class="metric-note">Invalid or unavailable tools</div>
            </div>
        </div>

        <section class="section">
            <div class="section-head">
                <h2>Condition Comparison</h2>
                <span class="small" id="modelName">—</span>
            </div>
            <div id="comparison"></div>
        </section>

        <section class="section">
            <div class="section-head">
                <h2>Model Status</h2>
                <span class="small" id="reportTime">—</span>
            </div>
            <div id="conditionStatus"></div>
        </section>
    </section>

    <section id="metrics" class="hidden">
        <section class="section">
            <div class="section-head"><h2>Performance Metrics</h2></div>
            <div class="table-wrap">
                <table>
                    <thead><tr><th>Condition</th><th>Correct</th><th>Accuracy</th><th>Avg. Latency</th><th>Avg. Tokens</th><th>Avg. Turns</th></tr></thead>
                    <tbody id="metricsRows"></tbody>
                </table>
            </div>
        </section>
    </section>

    <section id="tasks" class="hidden">
        <section class="section">
            <div class="section-head">
                <h2>Task Results</h2>
                <span class="small" id="taskCount">—</span>
            </div>
            <div class="table-wrap">
                <table>
                    <thead><tr><th>Task</th><th>Answer</th><th>Retrieval</th><th>Turns</th><th>Latency</th><th>Response</th></tr></thead>
                    <tbody id="taskRows"></tbody>
                </table>
            </div>
        </section>
    </section>

    <section class="section">
        <div class="section-head">
            <h2>Evaluation Run</h2>
            <span class="pill" id="runStatus">IDLE</span>
        </div>
        <div id="runMessage" class="small">Ready</div>
        <pre class="log" id="runLog">No active run.</pre>
    </section>

    <footer>
        <span>Agent Lab</span>
        <span id="footerReport">No report selected</span>
    </footer>
</main>
</div>
<div id="toast"></div>

<script>
const $ = id => document.getElementById(id);
const names = {
    baseline: "Direct Context",
    tool: "Tool Retrieval",
    memory: "Persistent Memory"
};
let reports = [];
let report = null;
let poller = null;

function esc(v) {
    return String(v ?? "").replace(/[&<>"']/g, c => ({
        "&":"&amp;", "<":"&lt;", ">":"&gt;",
        '"':"&quot;", "'":"&#39;"
    }[c]));
}
function seconds(v) {
    return Number.isFinite(Number(v)) ? (Number(v)/1000).toFixed(2)+" s" : "—";
}
function date(v) {
    if (!v) return "—";
    const d = new Date(v);
    return Number.isNaN(d.getTime()) ? String(v) : d.toLocaleString();
}
function toast(msg) {
    $("toast").textContent = msg;
    $("toast").classList.add("show");
    setTimeout(() => $("toast").classList.remove("show"), 2800);
}
async function api(url, options={}) {
    const response = await fetch(url, options);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Request failed");
    return data;
}
function showTab(tab) {
    ["overview","metrics","tasks"].forEach(id => $(id).classList.toggle("hidden", id !== tab));
    document.querySelectorAll("nav button").forEach(b =>
        b.classList.toggle("active", b.dataset.tab === tab)
    );
}
function summarize(rows) {
    const n = rows.length;
    const correct = rows.filter(r => r.answer_correct === true).length;
    const needed = rows.filter(r => r.retrieval_required === true);
    const retrieved = needed.filter(r => r.retrieval_success === true).length;
    const sum = key => rows.reduce((a,r) => a + (Number(r[key]) || 0), 0);
    return {
        n, correct,
        accuracy: n ? correct/n*100 : 0,
        latency: n ? sum("latency_ms")/n : 0,
        tokens: n ? sum("total_tokens")/n : 0,
        turns: n ? sum("turns_used")/n : 0,
        retrieval: needed.length ? retrieved/needed.length*100 : null,
        executed: sum("executed_tool_calls"),
        rejected: sum("rejected_tool_calls")
    };
}
function allStats() {
    const results = report?.results || {};
    return Object.keys(names).map(key => ({
        key, name: names[key], ...summarize(results[key] || []),
        rows: results[key] || []
    })).filter(x => x.n);
}
function renderReport() {
    if (!report) return;
    const stats = allStats();
    const best = [...stats].sort((a,b) => b.accuracy-a.accuracy)[0];
    const selectedKey = $("conditionSelect").value;
    const selected = stats.find(x => x.key === selectedKey);
    $("modelName").textContent = report.model || "—";
    $("reportTime").textContent = date(report.timestamp_utc);
    $("footerReport").textContent = $("reportSelect").value || "No report selected";

    $("bestAccuracy").textContent = best ? best.accuracy.toFixed(1)+"%" : "—";
    $("bestNote").textContent = best ? best.name+" · "+best.correct+"/"+best.n : "No results";
    $("avgLatency").textContent = selected ? seconds(selected.latency) : "—";
    $("avgTokens").textContent = selected ? Math.round(selected.tokens).toLocaleString() : "—";
    $("retrieval").textContent = selected && selected.retrieval !== null
        ? selected.retrieval.toFixed(1)+"%" : "N/A";
    $("executedCalls").textContent = selected ? selected.executed : "—";
    $("rejectedCalls").textContent = selected ? selected.rejected : "—";

    $("comparison").innerHTML = stats.map(s => `
        <div class="bar-row">
            <div>${esc(s.name)}</div>
            <div class="track"><div class="fill ${s.key}" style="width:${s.accuracy}%"></div></div>
            <div class="right">${s.correct}/${s.n}</div>
        </div>`).join("") || '<div class="empty">No results</div>';

    $("conditionStatus").innerHTML = stats.map(s => `
        <div class="status-row">
            <div><div class="status-name">${esc(s.name)}</div>
                <div class="status-detail">${s.correct}/${s.n} correct · ${seconds(s.latency)} avg.</div>
            </div>
            <span class="pill ${s.accuracy >= 80 ? "good" : s.accuracy >= 50 ? "warn" : "bad"}">
                ${s.accuracy.toFixed(1)}%
            </span>
            <div class="right small">${Math.round(s.tokens).toLocaleString()} tokens</div>
        </div>`).join("") || '<div class="empty">No results</div>';

    $("metricsRows").innerHTML = stats.map(s => `
        <tr><td>${esc(s.name)}</td><td>${s.correct}/${s.n}</td>
        <td>${s.accuracy.toFixed(1)}%</td><td>${seconds(s.latency)}</td>
        <td>${Math.round(s.tokens).toLocaleString()}</td><td>${s.turns.toFixed(2)}</td></tr>
    `).join("");

    renderTasks();
}
function renderTasks() {
    if (!report) return;
    const key = $("conditionSelect").value;
    const rows = (report.results || {})[key] || [];
    $("taskCount").textContent = rows.length+" tasks";
    $("taskRows").innerHTML = rows.map(r => `
        <tr>
            <td><strong>${esc(r.task_id)}</strong></td>
            <td><span class="pill ${r.answer_correct ? "good":"bad"}">${r.answer_correct ? "PASS":"FAIL"}</span></td>
            <td>${!r.retrieval_required ? '<span class="pill">N/A</span>' :
                `<span class="pill ${r.retrieval_success ? "good":"bad"}">${r.retrieval_success ? "PASS":"FAIL"}</span>`}</td>
            <td>${esc(r.turns_used)}</td>
            <td>${seconds(r.latency_ms)}</td>
            <td class="answer">${esc(r.agent_answer)}</td>
        </tr>`).join("") || '<tr><td colspan="6" class="empty">No task results</td></tr>';
}
async function loadReports() {
    const data = await api("/api/reports");
    reports = data.reports || [];
    const sel = $("reportSelect");
    const previous = sel.value;
    sel.innerHTML = "";
    if (!reports.length) {
        sel.innerHTML = '<option value="">No reports found</option>';
        report = null;
        $("modelName").textContent = "No report";
        $("comparison").innerHTML = '<div class="empty">Run an evaluation to view results.</div>';
        $("conditionStatus").innerHTML = '<div class="empty">No results</div>';
        return;
    }
    reports.forEach(r => {
        const opt = document.createElement("option");
        opt.value = r.name;
        opt.textContent = r.name.replace("report_","").replace(".json","");
        sel.appendChild(opt);
    });
    sel.value = reports.some(r => r.name === previous) ? previous : reports[0].name;
    await loadReport();
}
async function loadReport() {
    const name = $("reportSelect").value;
    if (!name) return;
    report = await api("/api/report?name="+encodeURIComponent(name));
    renderReport();
}
async function startRun() {
    if (!confirm("Run the full evaluation?")) return;
    try {
        await api("/api/run", {method:"POST"});
        toast("Evaluation started");
        if (!poller) poller = setInterval(loadStatus, 1200);
        await loadStatus();
    } catch(e) { toast(e.message); }
}
async function loadStatus() {
    try {
        const s = await api("/api/status");
        $("runStatus").textContent = s.running ? "RUNNING" :
            s.exit_code === 0 ? "COMPLETED" :
            s.exit_code !== null ? "FAILED" : "IDLE";
        $("runStatus").className = "pill "+(s.running ? "purple" : s.exit_code===0 ? "good" : s.exit_code!==null ? "bad" : "");
        $("runBtn").disabled = !!s.running;
        $("runBtn").textContent = s.running ? "Running…" : "Run Evaluation";
        $("runMessage").textContent = s.error || (s.running ? "Evaluation in progress" :
            s.finished_at ? "Finished "+date(s.finished_at) : "Ready");
        $("runLog").textContent = (s.log || []).join("\n") || "No active run.";
        $("runLog").scrollTop = $("runLog").scrollHeight;
        if (!s.running && poller) {
            clearInterval(poller); poller = null;
            if (s.exit_code === 0) {
                await loadReports();
                toast("Evaluation completed");
            }
        }
    } catch(e) {}
}
$("conditionSelect").addEventListener("change", renderReport);
loadReports().catch(e => toast(e.message));
loadStatus();
setInterval(loadStatus, 3500);
</script>
</body>
</html>"""


def get_reports():
    RESULTS.mkdir(exist_ok=True)
    files = sorted(
        RESULTS.glob("report_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return [
        {"name": p.name, "modified": p.stat().st_mtime}
        for p in files
    ]


def log_line(line):
    with LOCK:
        STATE["log"].append(line.rstrip())
        STATE["log"] = STATE["log"][-400:]


def run_evaluation():
    global PROCESS
    try:
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        process = subprocess.Popen(
            [sys.executable, "-u", str(SRC / "run_eval.py")],
            cwd=SRC,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=env,
        )
        with LOCK:
            PROCESS = process

        assert process.stdout is not None
        for line in process.stdout:
            log_line(line)

        code = process.wait()
        with LOCK:
            STATE["exit_code"] = code
            STATE["finished_at"] = datetime.now().astimezone().isoformat(
                timespec="seconds"
            )
            STATE["running"] = False
            STATE["error"] = None if code == 0 else f"Exit code: {code}"
    except Exception as exc:
        log_line(f"Error: {type(exc).__name__}: {exc}")
        with LOCK:
            STATE["exit_code"] = -1
            STATE["running"] = False
            STATE["error"] = str(exc)
    finally:
        with LOCK:
            PROCESS = None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/":
            body = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        elif parsed.path == "/api/reports":
            self.send_json({"reports": get_reports()})

        elif parsed.path == "/api/report":
            name = parse_qs(parsed.query).get("name", [""])[0]
            if (
                not name or Path(name).name != name
                or not name.startswith("report_")
                or not name.endswith(".json")
            ):
                self.send_json({"error": "Invalid report name"}, 400)
                return

            path = RESULTS / name
            if not path.is_file():
                self.send_json({"error": "Report not found"}, 404)
                return

            try:
                self.send_json(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError) as exc:
                self.send_json({"error": str(exc)}, 500)

        elif parsed.path == "/api/status":
            with LOCK:
                snapshot = {**STATE, "log": STATE["log"][-250:]}
            self.send_json(snapshot)

        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        if urlparse(self.path).path != "/api/run":
            self.send_json({"error": "Not found"}, 404)
            return

        with LOCK:
            if STATE["running"]:
                self.send_json({"error": "Evaluation already running"}, 409)
                return

            STATE.update({
                "running": True,
                "log": ["Starting evaluation…"],
                "exit_code": None,
                "error": None,
                "started_at": datetime.now().astimezone().isoformat(
                    timespec="seconds"
                ),
                "finished_at": None,
            })

        threading.Thread(target=run_evaluation, daemon=True).start()
        self.send_json({"ok": True}, 202)


def main():
    RESULTS.mkdir(exist_ok=True)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}"
    print(f"Agent Lab: {url}")
    print("Press Ctrl+C to stop.")

    threading.Timer(0.7, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
