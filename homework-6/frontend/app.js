/**
 * frontend/app.js — static, no-build-step dashboard for the transaction
 * processing pipeline.
 *
 * Purely a read-only viewer: it fetches shared/results/summary.json and the
 * individual shared/results/<transaction_id>.json files, and renders counts
 * by outcome plus a per-transaction table. It never writes to shared/ and
 * never triggers a pipeline run itself. It never renders source_account,
 * destination_account, or description.
 *
 * Run: serve the repo root with a static file server (e.g.
 * `python -m http.server 8000` from the repo root) so that this page's
 * fetch() calls to "/shared/results/..." resolve against the real
 * shared/results/ directory, then open http://localhost:8000/frontend/.
 * See HOWTORUN.md for the exact command.
 */

const RESULTS_BASE = "/shared/results";
const KNOWN_OUTCOMES = ["CLEARED", "HELD_FOR_REVIEW", "REJECTED"];

async function fetchJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`${path} -> HTTP ${response.status}`);
  }
  return response.json();
}

function renderCounts(summary) {
  const countsEl = document.getElementById("outcome-counts");
  countsEl.innerHTML = "";
  const counts = summary.outcome_counts || {};

  const allOutcomes = new Set([...KNOWN_OUTCOMES, ...Object.keys(counts)]);
  for (const outcome of allOutcomes) {
    const card = document.createElement("div");
    card.className = `count-card outcome-${outcome.toLowerCase()}`;
    const value = document.createElement("div");
    value.className = "count-value";
    value.textContent = String(counts[outcome] || 0);
    const label = document.createElement("div");
    label.className = "count-label";
    label.textContent = outcome.replace(/_/g, " ");
    card.append(value, label);
    countsEl.appendChild(card);
  }

  document.getElementById("total-count").textContent = summary.total ?? 0;

  const reasonsEl = document.getElementById("reason-codes");
  reasonsEl.innerHTML = "";
  const reasons = summary.reason_code_counts || {};
  const reasonKeys = Object.keys(reasons);
  if (reasonKeys.length === 0) {
    const li = document.createElement("li");
    li.className = "reason-empty";
    li.textContent = "No rejections or holds in this run.";
    reasonsEl.appendChild(li);
  } else {
    for (const reason of reasonKeys) {
      const li = document.createElement("li");
      li.textContent = `${reason}: ${reasons[reason]}`;
      reasonsEl.appendChild(li);
    }
  }
}

async function fetchTransactionRow(transactionId) {
  try {
    const record = await fetchJson(`${RESULTS_BASE}/${encodeURIComponent(transactionId)}.json`);
    const data = record.data || {};
    return {
      id: data.transaction_id || transactionId,
      outcome: data.outcome || data.status || "UNKNOWN",
      reason: data.reason_code || "",
      risk: data.risk_level || "",
    };
  } catch (err) {
    return { id: transactionId, outcome: "ERROR", reason: String(err.message || err), risk: "" };
  }
}

async function renderTable(summary) {
  const tbody = document.querySelector("#results-table tbody");
  tbody.innerHTML = "";
  const ids = summary.transaction_ids || [];

  const rows = await Promise.all(ids.map(fetchTransactionRow));

  for (const row of rows) {
    const tr = document.createElement("tr");

    const idCell = document.createElement("td");
    idCell.textContent = row.id;

    const outcomeCell = document.createElement("td");
    outcomeCell.textContent = row.outcome;
    outcomeCell.className = `outcome-${row.outcome.toLowerCase()}`;

    const reasonCell = document.createElement("td");
    reasonCell.textContent = row.reason;

    const riskCell = document.createElement("td");
    riskCell.textContent = row.risk;

    tr.append(idCell, outcomeCell, reasonCell, riskCell);
    tbody.appendChild(tr);
  }
}

async function renderDashboard() {
  const statusEl = document.getElementById("status-message");
  statusEl.textContent = "Loading...";
  try {
    const summary = await fetchJson(`${RESULTS_BASE}/summary.json`);
    renderCounts(summary);
    await renderTable(summary);
    const generatedAt = summary.generated_at || "unknown";
    statusEl.textContent = `Loaded. Pipeline run generated at ${generatedAt}. Last refreshed ${new Date().toLocaleTimeString()}.`;
  } catch (err) {
    statusEl.textContent =
      `Unable to load shared/results/summary.json (${err.message}). ` +
      "Run the pipeline first (python orchestrator.py) and serve this page from the repo root " +
      "(e.g. python -m http.server 8000), then open http://localhost:8000/frontend/.";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  renderDashboard();
  document.getElementById("refresh-button").addEventListener("click", renderDashboard);
});
