const state = {
  tf: "15m",
  limit: 20,
  excludeStables: true,
  selectedAsset: null,
  summaryRequestId: 0,
};

const rankingConfig = {
  top_borrow_pressure_usdt: {
    value: "borrow_pressure_usdt",
    percent: "borrow_pressure_percent",
    label: "Borrow USDT",
  },
  top_borrow_pressure_percent: {
    value: "borrow_pressure_percent",
    percent: "borrow_pressure_usdt",
    label: "Borrow %",
  },
  top_recovery_usdt: {
    value: "recovery_usdt",
    percent: "recovery_percent",
    label: "Recovery USDT",
  },
  top_recovery_percent: {
    value: "recovery_percent",
    percent: "recovery_usdt",
    label: "Recovery %",
  },
};

function el(id) {
  return document.getElementById(id);
}

function showError(message) {
  const panel = el("error-panel");
  panel.textContent = message;
  panel.hidden = false;
}

function clearError() {
  const panel = el("error-panel");
  panel.textContent = "";
  panel.hidden = true;
}

function setLoading(isLoading) {
  const indicator = el("loading-indicator");
  const refresh = el("refresh");
  indicator.hidden = !isLoading;
  refresh.disabled = isLoading;
  refresh.textContent = isLoading ? "Refreshing..." : "Refresh";
}

async function getJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${url} returned ${response.status}: ${text.slice(0, 300)}`);
  }
  return response.json();
}

function compactDecimal(value) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }

  const text = String(value);
  if (/^-?0(?:\.0+)?(?:e-\d+)?$/i.test(text)) {
    return "0";
  }

  const number = Number(text);
  if (!Number.isFinite(number)) {
    return text.length <= 16 ? text : `${text.slice(0, 12)}...`;
  }

  const abs = Math.abs(number);
  const format = (divisor, suffix) => `${(number / divisor).toFixed(abs >= divisor * 10 ? 1 : 2).replace(/\.?0+$/, "")}${suffix}`;

  if (abs >= 1_000_000_000) {
    return format(1_000_000_000, "B");
  }
  if (abs >= 1_000_000) {
    return format(1_000_000, "M");
  }
  if (abs >= 1_000) {
    return format(1_000, "K");
  }
  if (abs > 0 && abs < 0.000001) {
    return number.toExponential(2);
  }
  return text.length <= 12 ? text : number.toLocaleString("en-US", { maximumFractionDigits: 6 });
}

function compactTimestamp(value) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  const text = String(value);
  const date = new Date(text);
  if (Number.isNaN(date.getTime())) {
    return text.length <= 19 ? text : `${text.slice(0, 19)}...`;
  }
  const pad = (part) => String(part).padStart(2, "0");
  return `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())} ${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())} UTC`;
}

function cell(value, type = "decimal") {
  const text = value === null || value === undefined || value === "" ? "-" : String(value);
  const display = type === "timestamp" ? compactTimestamp(value) : compactDecimal(value);
  return `<span title="${escapeHtml(text)}">${escapeHtml(display)}</span>`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function freshnessRows(freshness) {
  const rows = [
    ["latest_metrics_calculated_at", freshness.latest_metrics_calculated_at, "timestamp"],
    ["latest_snapshot_at", freshness.latest_snapshot_at, "timestamp"],
    ["latest_metrics_age_seconds", freshness.latest_metrics_age_seconds],
    ["latest_snapshot_age_seconds", freshness.latest_snapshot_age_seconds],
    ["last_collector_run_status", freshness.last_collector_run_status],
    ["last_collector_run_finished_at", freshness.last_collector_run_finished_at, "timestamp"],
    ["is_data_stale", freshness.is_data_stale],
    ["stale_after_seconds", freshness.stale_after_seconds],
  ];
  return rows
    .map(([key, value, type]) => `<div><dt>${escapeHtml(key)}</dt><dd>${cell(value, type)}</dd></div>`)
    .join("");
}

function renderFreshness(freshness) {
  el("freshness-grid").innerHTML = freshnessRows(freshness);
  const message = freshness.is_data_stale
    ? "Data is stale. Collector may not be running or latest cycle is older than threshold."
    : "Data is fresh.";
  el("freshness-message").textContent = message;

  const pill = el("freshness-pill");
  pill.textContent = freshness.is_data_stale ? "Data stale" : "Data fresh";
  pill.className = freshness.is_data_stale ? "pill pill-stale" : "pill pill-fresh";
  el("freshness-message").className = freshness.is_data_stale ? "stale-text" : "fresh-text";
}

function renderRankingTable(targetId, items) {
  const target = el(targetId);
  const config = rankingConfig[targetId];
  if (!items || items.length === 0) {
    target.innerHTML = `<p class="empty-state">No rows for this ranking.</p>`;
    return;
  }

  const rows = items
    .map(
      (item) => `
        <tr>
          <td><button class="asset-link" data-asset="${escapeHtml(item.asset)}">${escapeHtml(item.asset)}</button></td>
          <td>${cell(item[config.value])}</td>
          <td>${cell(item[config.percent])}</td>
          <td>${cell(item.current_available_inventory)}</td>
          <td>${cell(item.previous_available_inventory)}</td>
          <td>${cell(item.net_pool_change_percent)}</td>
          <td>${cell(item.spot_price_usdt)}</td>
          <td>${cell(item.price_symbol)}</td>
          <td>${cell(item.current_snapshot_at, "timestamp")}</td>
        </tr>
      `
    )
    .join("");

  target.innerHTML = `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
          <th>Asset</th>
          <th>${escapeHtml(config.label)}</th>
            <th>Other metric</th>
            <th>Current inv.</th>
            <th>Previous inv.</th>
            <th>Net change %</th>
            <th>Spot USDT</th>
            <th>Symbol</th>
            <th>Snapshot</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

function renderSummary(summary) {
  renderFreshness(summary.data_freshness);
  for (const [key, items] of Object.entries(summary.rankings)) {
    renderRankingTable(key, items);
  }
}

function renderMetricsHistory(items) {
  if (!items || items.length === 0) {
    el("metrics-history").innerHTML = `<p class="empty-state">No metric history for this asset/timeframe.</p>`;
    return;
  }
  const rows = items
    .map(
      (item) => `
        <tr>
          <td>${cell(item.calculated_at, "timestamp")}</td>
          <td>${cell(item.borrow_pressure_usdt)}</td>
          <td>${cell(item.borrow_pressure_percent)}</td>
          <td>${cell(item.recovery_usdt)}</td>
          <td>${cell(item.recovery_percent)}</td>
          <td>${cell(item.current_available_inventory)}</td>
        </tr>
      `
    )
    .join("");
  el("metrics-history").innerHTML = `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Calculated</th>
            <th>Borrow USDT</th>
            <th>Borrow %</th>
            <th>Recovery USDT</th>
            <th>Recovery %</th>
            <th>Current inventory</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

function renderPoolHistory(items) {
  if (!items || items.length === 0) {
    el("pool-history").innerHTML = `<p class="empty-state">No pool history for this asset.</p>`;
    return;
  }
  const rows = items
    .map(
      (item) => `
        <tr>
          <td>${cell(item.snapshot_at, "timestamp")}</td>
          <td>${cell(item.pool_type)}</td>
          <td>${cell(item.available_inventory)}</td>
          <td>${cell(item.source)}</td>
        </tr>
      `
    )
    .join("");
  el("pool-history").innerHTML = `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Snapshot</th>
            <th>Pool type</th>
            <th>Available inventory</th>
            <th>Source</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

async function loadSummary() {
  clearError();
  const requestId = ++state.summaryRequestId;
  setLoading(true);
  state.tf = el("timeframe").value;
  state.limit = Math.min(100, Math.max(1, Number(el("limit").value || 20)));
  el("limit").value = state.limit;
  state.excludeStables = el("exclude-stables").checked;

  const url = `/api/scanner/summary?tf=${encodeURIComponent(state.tf)}&limit=${state.limit}&exclude_stables=${state.excludeStables}`;
  try {
    const [health, summary] = await Promise.all([getJson("/health"), getJson(url)]);
    if (requestId !== state.summaryRequestId) {
      return;
    }
    el("api-version").textContent = `API ${health.version || "unknown"}`;
    renderSummary(summary);
    if (state.selectedAsset) {
      await loadAssetDetail(state.selectedAsset);
    }
  } catch (error) {
    if (requestId === state.summaryRequestId) {
      showError(`Unable to load scanner summary. ${error.message}`);
    }
  } finally {
    if (requestId === state.summaryRequestId) {
      setLoading(false);
    }
  }
}

async function loadAssetDetail(asset) {
  clearError();
  state.selectedAsset = asset;
  el("asset-title").textContent = `Asset Details: ${asset}`;
  el("asset-detail").hidden = false;
  try {
    const [metrics, pool] = await Promise.all([
      getJson(`/api/assets/${encodeURIComponent(asset)}/metrics-history?tf=${encodeURIComponent(state.tf)}&limit=50`),
      getJson(`/api/assets/${encodeURIComponent(asset)}/pool-history?limit=50`),
    ]);
    renderMetricsHistory(metrics.items);
    renderPoolHistory(pool.items);
  } catch (error) {
    showError(`Unable to load asset detail for ${asset}. ${error.message}`);
  }
}

document.addEventListener("click", (event) => {
  const button = event.target.closest(".asset-link");
  if (button) {
    loadAssetDetail(button.dataset.asset);
  }
});

document.addEventListener("DOMContentLoaded", () => {
  el("timeframe").addEventListener("change", loadSummary);
  el("limit").addEventListener("input", debounce(loadSummary, 350));
  el("exclude-stables").addEventListener("change", loadSummary);
  el("refresh").addEventListener("click", loadSummary);
  loadSummary();
});

function debounce(callback, delayMs) {
  let timeoutId;
  return () => {
    window.clearTimeout(timeoutId);
    timeoutId = window.setTimeout(callback, delayMs);
  };
}
