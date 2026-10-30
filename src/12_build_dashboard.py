
from pathlib import Path
import csv
import json

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"
DASHBOARD = ROOT / "dashboard"
DASHBOARD.mkdir(parents=True, exist_ok=True)


def read_csv(filename):
    path = REPORTS / filename
    if not path.exists():
        raise FileNotFoundError(f"Missing report: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    summary = read_csv("eda_summary.csv")
    monthly = read_csv("monthly_delay.csv")
    airlines = read_csv("airline_delay.csv")

    if not summary:
        raise ValueError("EDA summary is empty.")

    data = {
        "summary": summary[0],
        "monthly": monthly,
        "airlines": airlines,
    }

    payload = json.dumps(data).replace("</", "<\\/")

    template = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FlightGraph | Flight Analytics</title>
<style>
:root {
  --bg: #f4f7fb;
  --card: #ffffff;
  --ink: #17243a;
  --muted: #65748b;
  --blue: #3268d8;
  --border: #e2e8f0;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: "Segoe UI", Arial, sans-serif;
}
header {
  padding: 30px 5%;
  background: #12213c;
  color: white;
}
header h1 { margin: 0 0 8px; font-size: 30px; }
header p { margin: 0; color: #ccd8eb; }
main { max-width: 1250px; margin: auto; padding: 24px; }
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 16px;
}
.card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 20px;
  margin-bottom: 18px;
  box-shadow: 0 3px 12px #1c33540a;
  min-width: 0;
}
.metric-label { color: var(--muted); font-size: 14px; }
.metric { font-size: 30px; font-weight: 700; margin-top: 10px; }
h2 { font-size: 19px; margin: 0 0 16px; }
.sub { color: var(--muted); font-size: 13px; line-height: 1.6; }
.charts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 400px), 1fr));
  gap: 18px;
  margin-top: 18px;
}
svg { display: block; width: 100%; height: auto; overflow: visible; }
.controls {
  display: flex; flex-wrap: wrap; gap: 14px; align-items: center;
  margin-bottom: 14px;
}
select {
  padding: 9px 12px; border: 1px solid var(--border);
  background: white; border-radius: 8px; color: var(--ink);
}
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { padding: 10px 8px; border-bottom: 1px solid var(--border); text-align: left; }
th { color: var(--muted); font-weight: 600; }
.table-wrap { overflow-x: auto; }
footer { color: var(--muted); padding: 20px 0; font-size: 12px; }
@media (max-width: 600px) {
  main { padding: 14px; }
  header { padding: 24px 18px; }
  header h1 { font-size: 25px; }
}
</style>
</head>
<body>
<header>
  <h1>✈ FlightGraph</h1>
  <p>Large-Scale Flight Delay Analytics · Powered by PySpark</p>
</header>

<main>
  <div class="grid">
    <div class="card">
      <div class="metric-label">Training Flight Records</div>
      <div class="metric" id="flights">—</div>
    </div>
    <div class="card">
      <div class="metric-label">Arrivals Delayed 15+ Minutes</div>
      <div class="metric" id="delayed">—</div>
    </div>
    <div class="card">
      <div class="metric-label">Delay Rate</div>
      <div class="metric" id="rate">—</div>
    </div>
    <div class="card">
      <div class="metric-label">Valid Delay Labels</div>
      <div class="metric" id="valid">—</div>
    </div>
  </div>

  <div class="charts">
    <section class="card">
      <h2>Arrival Delay Distribution</h2>
      <div id="distribution"></div>
      <p class="sub">
        Below threshold also includes early arrivals and delays shorter
        than 15 minutes.
      </p>
    </section>

    <section class="card">
      <h2>Monthly Delay Trend</h2>
      <div id="monthly"></div>
      <p class="sub">Share of records with ArrDel15 = 1, by year and month.</p>
    </section>
  </div>

  <section class="card" style="margin-top:18px">
    <h2>Airline Delay Comparison</h2>
    <div class="controls">
      <label>Minimum flight records:
        <select id="minimum">
          <option value="100000">100,000</option>
          <option value="250000">250,000</option>
          <option value="500000">500,000</option>
          <option value="1000000">1,000,000</option>
        </select>
      </label>
      <label>Airlines to show:
        <select id="topn">
          <option>5</option><option selected>10</option>
          <option>15</option><option>20</option>
        </select>
      </label>
    </div>
    <div id="airlines"></div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr><th>Airline</th><th>Flight records</th><th>15+ min delay</th></tr>
        </thead>
        <tbody id="airline-table"></tbody>
      </table>
    </div>
    <p class="sub">
      Comparison is based on the training dataset. A higher percentage
      does not by itself explain why delays occurred.
    </p>
  </section>

  <footer>
    FlightGraph · Descriptive analysis, not causal inference.
  </footer>
</main>

<script>
const DATA = __DATA__;

const fmt = n => Number(n).toLocaleString("en-US");
const num = v => Number(v);
const pct = v => `${num(v).toFixed(2)}%`;

const summary = DATA.summary;

document.getElementById("flights").textContent =
  fmt(summary.flight_records);
document.getElementById("delayed").textContent =
  fmt(summary.delayed_15min_or_more);
document.getElementById("rate").textContent =
  pct(summary.arrival_delay_15min_or_more_pct);
document.getElementById("valid").textContent =
  fmt(summary.valid_labels);

function distributionChart() {
  const delayed = num(summary.arrival_delay_15min_or_more_pct);
  const rows = [
    ["15+ minutes delayed", delayed],
    ["Below 15-minute threshold", 100 - delayed]
  ];
  let svg = `<svg viewBox="0 0 600 180" role="img"
    aria-label="Arrival delay distribution">`;

  rows.forEach((row, i) => {
    const y = 40 + i * 65;
    const width = row[1] * 3.4;
    svg += `<text x="4" y="${y}" font-size="14" fill="#17243a">${row[0]}</text>
      <rect x="4" y="${y + 10}" width="500" height="19" rx="5" fill="#e8eef8"/>
      <rect x="4" y="${y + 10}" width="${width}" height="19" rx="5" fill="#3268d8"/>
      <text x="515" y="${y + 25}" font-size="13" fill="#17243a">${row[1].toFixed(2)}%</text>`;
  });

  svg += "</svg>";
  document.getElementById("distribution").innerHTML = svg;
}

function monthlyChart() {
  const rows = DATA.monthly
    .map(r => ({
      label: `${r.Year}-${String(r.Month).padStart(2, "0")}`,
      value: num(r.delayed_15min_or_more_pct),
      year: num(r.Year),
      month: num(r.Month)
    }))
    .filter(r => Number.isFinite(r.value))
    .sort((a, b) => a.year - b.year || a.month - b.month);

  if (!rows.length) {
    document.getElementById("monthly").textContent = "No monthly data.";
    return;
  }

  const W = 700, H = 290;
  const L = 48, R = 15, T = 22, B = 45;
  const max = Math.max(5, Math.ceil(Math.max(...rows.map(r => r.value)) / 5) * 5);
  const x = i => L + i * (W - L - R) / Math.max(1, rows.length - 1);
  const y = v => H - B - (v / max) * (H - T - B);

  let s = `<svg viewBox="0 0 ${W} ${H}" role="img"
    aria-label="Monthly delay trend">`;

  for (let j = 0; j <= 4; j++) {
    const value = max * j / 4;
    s += `<line x1="${L}" y1="${y(value)}" x2="${W-R}" y2="${y(value)}"
      stroke="#e2e8f0"/>
      <text x="${L-8}" y="${y(value)+4}" font-size="12" text-anchor="end"
      fill="#65748b">${value.toFixed(0)}%</text>`;
  }

  const path = rows.map((r, i) =>
    `${i === 0 ? "M" : "L"} ${x(i)} ${y(r.value)}`
  ).join(" ");

  s += `<path d="${path}" fill="none" stroke="#3268d8" stroke-width="2.8"/>`;

  rows.forEach((r, i) => {
    s += `<circle cx="${x(i)}" cy="${y(r.value)}" r="3" fill="#3268d8">
      <title>${r.label}: ${r.value.toFixed(2)}%</title></circle>`;
  });

  const step = Math.max(1, Math.ceil(rows.length / 7));
  rows.forEach((r, i) => {
    if (i % step === 0 || i === rows.length - 1) {
      s += `<text x="${x(i)}" y="${H-17}" text-anchor="middle"
        font-size="11" fill="#65748b">${r.label}</text>`;
    }
  });

  s += "</svg>";
  document.getElementById("monthly").innerHTML = s;
}

function airlineChart() {
  const minimum = num(document.getElementById("minimum").value);
  const topn = num(document.getElementById("topn").value);

  const rows = DATA.airlines
    .map(r => ({
      code: r.Reporting_Airline,
      flights: num(r.flight_records),
      value: num(r.delayed_15min_or_more_pct)
    }))
    .filter(r =>
      r.flights >= minimum && Number.isFinite(r.value)
    )
    .sort((a, b) => b.value - a.value)
    .slice(0, topn);

  const chart = document.getElementById("airlines");
  const table = document.getElementById("airline-table");

  if (!rows.length) {
    chart.textContent = "No airlines match these filters.";
    table.innerHTML = "";
    return;
  }

  const max = Math.max(5, Math.ceil(Math.max(...rows.map(r => r.value)) / 5) * 5);
  const W = 700, rowH = 34, H = rows.length * rowH + 20;

  let svg = `<svg viewBox="0 0 ${W} ${H}" role="img"
    aria-label="Airline delay percentage comparison">`;

  rows.forEach((r, i) => {
    const y = 10 + i * rowH;
    const width = r.value / max * 460;
    svg += `<text x="4" y="${y+19}" font-size="13" fill="#17243a">${r.code}</text>
      <rect x="70" y="${y+5}" width="460" height="18" rx="4" fill="#e8eef8"/>
      <rect x="70" y="${y+5}" width="${width}" height="18" rx="4" fill="#3268d8"/>
      <text x="${Math.min(540, 78+width)}" y="${y+19}" font-size="12"
      fill="#17243a">${r.value.toFixed(2)}%</text>`;
  });

  svg += "</svg>";
  chart.innerHTML = svg;

  table.innerHTML = rows.map(r =>
    `<tr><td>${r.code}</td><td>${fmt(r.flights)}</td>
    <td>${r.value.toFixed(2)}%</td></tr>`
  ).join("");
}

distributionChart();
monthlyChart();
airlineChart();

document.getElementById("minimum").addEventListener("change", airlineChart);
document.getElementById("topn").addEventListener("change", airlineChart);
</script>
</body>
</html>
"""

    html = template.replace("__DATA__", payload)
    output = DASHBOARD / "flightgraph_dashboard.html"
    output.write_text(html, encoding="utf-8")

    print("FlightGraph dashboard generated successfully.")
    print(f"Monthly records loaded: {len(monthly)}")
    print(f"Airline records loaded: {len(airlines)}")
    print(f"Dashboard: {output}")


if __name__ == "__main__":
    main()
