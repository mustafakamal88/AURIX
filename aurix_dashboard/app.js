const REFRESH_MS = 5000;

const READ_ONLY_ENDPOINTS = {
  summary: "/operator/summary",
  status: "/operator/status",
  market: "/market/status",
  context: "/context/latest",
  paper: "/paper/status",
  analytics: "/analytics/paper/summary",
  journal: "/journal/status",
  aiReview: "/ai-review/latest",
  evidence: "/evidence/latest",
  forward: "/forward-test/status",
  orchestrator: "/orchestrator/status",
  daemon: "/daemon/status",
  longForward: "/long-forward-test/status",
  liveReadiness: "/live-readiness/status"
};

function byId(id) {
  return document.getElementById(id);
}

function text(id, value) {
  byId(id).textContent = value === undefined || value === null || value === "" ? "--" : String(value);
}

function boolText(value) {
  return value ? "true" : "false";
}

function fixed(value, digits = 2) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(digits) : "--";
}

async function getJson(url) {
  const response = await fetch(url, { method: "GET", cache: "no-store" });
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`${url} returned ${response.status}`);
  }
  return response.json();
}

async function readAll() {
  const entries = await Promise.all(
    Object.entries(READ_ONLY_ENDPOINTS).map(async ([key, url]) => {
      try {
        return [key, await getJson(url)];
      } catch (error) {
        return [key, { error: error.message }];
      }
    })
  );
  return Object.fromEntries(entries);
}

function latestSignal(status, strategyName) {
  const latest = status?.strategy?.latest_signal;
  const latestV2 = status?.strategy?.latest_signal_v2;
  if (strategyName === "xauusd_paper_v2") {
    return latestV2 || {};
  }
  return latest?.strategy_name === strategyName ? latest : {};
}

function collectWarnings(data) {
  const warnings = [];
  warnings.push(...(data.summary?.warnings || []));
  warnings.push(...(data.market?.quality?.reasons || []));
  warnings.push(...(data.status?.market?.quality?.reasons || []));
  warnings.push(...(data.evidence?.warnings || []));
  warnings.push(...(data.evidence?.blocking_reasons || []));
  warnings.push(...(data.liveReadiness?.latest?.warnings || []));
  warnings.push(...(data.liveReadiness?.latest?.blocking_reasons || []));
  warnings.push(...(data.status?.strategy?.latest_signal?.reasons || []));
  warnings.push(...(data.status?.strategy?.latest_signal_v2?.reasons || []));
  for (const [key, value] of Object.entries(data)) {
    if (value?.error) {
      warnings.push(`${key}: ${value.error}`);
    }
  }
  return [...new Set(warnings.filter(Boolean).map(String))];
}

function renderWarnings(items) {
  const list = byId("warnings");
  list.innerHTML = "";
  if (!items.length) {
    const item = document.createElement("li");
    item.className = "ok";
    item.textContent = "No warnings reported.";
    list.appendChild(item);
    return;
  }
  for (const warning of items) {
    const item = document.createElement("li");
    item.textContent = warning;
    list.appendChild(item);
  }
}

function render(data) {
  const status = data.status || {};
  const summary = data.summary || {};
  const account = status.account || {};
  const market = status.market || {};
  const context = data.context || status.context?.latest || {};
  const safety = status.safety || {};
  const strategy = status.strategy || {};
  const latestV1 = latestSignal(status, "xauusd_paper_v1");
  const latestV2 = latestSignal(status, "xauusd_paper_v2");
  const comparison = status.backtest?.compare_v1_v2 || {};
  const paper = data.paper || status.paper || {};
  const analytics = data.analytics || status.analytics || {};
  const forward = data.forward || status.forward_test || {};
  const campaign = forward.campaign || {};
  const progress = campaign.progress || {};
  const evidence = data.evidence || status.evidence?.latest || {};
  const daemon = data.daemon || status.daemon || {};
  const orchestrator = data.orchestrator || status.orchestrator || {};
  const longForward = data.longForward || status.long_forward_test || {};
  const liveReadinessStatus = data.liveReadiness || status.live_readiness || {};
  const liveReadiness = liveReadinessStatus.latest || {};
  const aiReview = data.aiReview || {};

  text("service", status.service || "aurix-mac-wine-bridge");
  text("mode", summary.mode || "PAPER");
  text("symbol", summary.symbol || market.symbol);
  text("liveTrading", safety.live_trading_enabled ? "ENABLED" : "DISABLED");
  text("paperOnly", boolText(safety.paper_only !== false));

  text("balance", fixed(account.balance));
  text("equity", fixed(account.equity));
  text("currency", account.currency);

  text("bid", fixed(market.bid, 3));
  text("ask", fixed(market.ask, 3));
  text("spread", market.spread_points);
  text("marketQuality", market.quality?.ok ? "OK" : "NOT OK");

  text("session", context.session_name || summary.session);
  text("sessionAllowed", boolText(orchestrator.session_allowed || summary.orchestrator_session_allowed));
  text("regime", context.regime || summary.regime);
  text("bias", context.directional_bias || context.context_bias);

  text("v1Signal", latestV1.status);
  text("v2Signal", latestV2.status || summary.v2_signal_status);
  text("v2Direction", latestV2.direction);
  text("v2Reasons", (latestV2.reasons || []).join("; "));
  text(
    "comparison",
    comparison.v2
      ? `V1 ${comparison.v1?.trades ?? "--"} trades / ${comparison.v1?.expectancy_r ?? "--"}R, V2 ${comparison.v2?.trades ?? "--"} trades / ${comparison.v2?.expectancy_r ?? "--"}R`
      : "No comparison report"
  );

  text("paperOpen", paper.open_trades);
  text("paperClosed", analytics.closed_trades ?? paper.closed_trades);
  text("winRate", analytics.win_rate ?? summary.paper_win_rate);
  text("expectancy", analytics.expectancy_r ?? summary.paper_expectancy_r);

  text("forwardStatus", campaign.status || summary.forward_test_status);
  text("forwardProgress", `${progress.percent ?? summary.forward_test_progress_percent ?? 0}%`);
  text("forwardCandles", campaign.candles_recorded ?? forward.candles_recorded);
  text("forwardClosed", campaign.closed_paper_trades ?? summary.forward_test_closed_paper_trades);

  text("evidenceStatus", evidence.status);
  text("liveReady", boolText(evidence.live_ready));
  text("blockingReasons", (evidence.blocking_reasons || []).join("; "));

  text("orchestratorRunning", boolText(orchestrator.running));
  text("daemonRunning", boolText(daemon.running));
  text("daemonLoops", daemon.loop_count);
  text("daemonHeartbeat", daemon.last_heartbeat_at);

  text("longRunning", boolText(longForward.running));
  text("longSession", longForward.current_session);
  text("longProgress", `${longForward.forward_test_progress ?? 0}%`);
  text("longCandles", longForward.recorded_candles);
  text("longClosed", longForward.paper_closed_trades);
  text("longEvidence", longForward.evidence_status);
  text("longDailyReport", longForward.daily_report_generated_at);

  text("liveReadinessStatus", liveReadiness.status);
  text("liveReadinessScore", liveReadiness.score);
  text("liveReadinessArming", boolText(liveReadiness.live_arming_allowed));
  text("liveReadinessExecution", boolText(liveReadiness.live_execution_allowed));
  text("liveReadinessBlocks", (liveReadiness.blocking_reasons || []).join("; "));
  text("liveReadinessChecklist", (liveReadiness.manual_requirements || []).length || (liveReadinessStatus.config ? 10 : 0));

  text("aiSummary", aiReview.summary || status.ai_review?.latest_summary);
  text("aiActions", aiReview.action_items_count || status.ai_review?.latest_action_items_count || 0);

  renderWarnings(collectWarnings(data));
  text("updatedAt", `Last refreshed ${new Date().toLocaleTimeString()}. Dashboard is read-only.`);
}

async function refresh() {
  const data = await readAll();
  render(data);
}

refresh();
setInterval(refresh, REFRESH_MS);
