"use strict";

const REFRESH_MS = 5000;
const RUNTIME_SUMMARY_ENDPOINT = "/dashboard/runtime-summary";

// ── DOM helpers ──────────────────────────────────────────────────

function byId(id) {
  return document.getElementById(id);
}

function safeStr(value) {
  return value === undefined || value === null || value === "" ? "--" : String(value);
}

function setText(id, value) {
  const el = byId(id);
  if (!el) return;
  el.textContent = safeStr(value);
}

function setHTML(id, html) {
  const el = byId(id);
  if (!el) return;
  el.innerHTML = html;
}

function fixed(value, digits = 2) {
  const n = Number(value);
  return Number.isFinite(n) ? n.toFixed(digits) : "--";
}

function joinItems(items) {
  if (!Array.isArray(items) || !items.length) return "--";
  return items.map(String).join("; ");
}

function shortId(id) {
  if (!id || typeof id !== "string") return "--";
  return id.length > 14 ? id.slice(0, 8) + "…" + id.slice(-5) : id;
}

function fmtTime(value) {
  if (!value) return "--";
  const s = String(value);
  // If it looks like a full ISO datetime, show just the time portion
  if (/^\d{4}-\d{2}-\d{2}T/.test(s)) {
    try {
      return new Date(s).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    } catch (_) { /* fall through */ }
  }
  return s;
}

// ── Status badge rendering ────────────────────────────────────────

// Returns a color class string for a status-like text value
function statusColor(value) {
  if (value === undefined || value === null || value === "" || value === "--") return "";
  const v = String(value).toUpperCase().trim();
  const GOOD_SET = new Set(["OK", "CLEAN", "SAFE", "HEALTHY", "PASS", "PASSED", "ACTIVE", "CERTIFIED", "VALID", "TRUE", "ENABLED", "SUCCESS", "READY"]);
  const WARN_SET = new Set(["WARNING", "WARN", "DEGRADED", "STALE", "PARTIAL", "COLLECTING", "PENDING"]);
  const DANGER_SET = new Set(["ERROR", "BLOCKED", "LOCKED", "DISABLED", "FAIL", "FAILED", "CORRUPT", "CORRUPTED", "INVALID", "FALSE", "MISSING", "UNKNOWN"]);
  const BLUE_SET = new Set(["RUNNING", "WAITING", "MONITORING", "EVALUATING", "SCANNING", "ACTIVE", "LIVE"]);

  if (GOOD_SET.has(v)) return "good";
  if (WARN_SET.has(v)) return "warn";
  if (DANGER_SET.has(v)) return "danger";
  if (BLUE_SET.has(v)) return "blue";
  return "";
}

function pillHTML(value, colorClass) {
  const cls = colorClass || statusColor(value);
  const display = safeStr(value);
  if (display === "--") return "--";
  if (!cls) return `<span class="pill neutral">${display}</span>`;
  return `<span class="pill ${cls}">${display}</span>`;
}

// Set a status badge in an rt-value element
function setStatus(id, value, colorClass) {
  const el = byId(id);
  if (!el) return;
  el.innerHTML = pillHTML(value, colorClass);
}

// For boolean safety flags: false = LOCKED/DISABLED = good (this system is always locked)
// invertSafe=true means false is shown as green "DISABLED", true as red "ENABLED"
function setSafetyBool(id, value, { invertSafe = false } = {}) {
  const el = byId(id);
  if (!el) return;
  if (value === undefined || value === null) { el.textContent = "--"; return; }
  if (invertSafe) {
    // false = green locked, true = red enabled (bad for execution flags)
    el.innerHTML = value
      ? pillHTML("ENABLED", "danger")
      : pillHTML("DISABLED", "good");
  } else {
    // false = green (session had no activity), true = red (session created something)
    el.innerHTML = value
      ? pillHTML("true", "danger")
      : pillHTML("false", "good");
  }
}

// Session safety: false = green (no activity created), true = red (activity!)
function setSessionBool(id, value) {
  setSafetyBool(id, value, { invertSafe: false });
}

// Execution lock: false = good (locked), true = danger (enabled — unexpected)
function setExecLock(id, value) {
  setSafetyBool(id, value, { invertSafe: true });
}

// Overall session safe: true = green, false = danger
function setOverallSafe(id, value) {
  const el = byId(id);
  if (!el) return;
  if (value === undefined || value === null) { el.textContent = "--"; return; }
  el.innerHTML = value
    ? pillHTML("SAFE", "good")
    : pillHTML("UNSAFE", "danger");
}

// ── Connection state ──────────────────────────────────────────────

let _connected = true;

function setConnected(ok, reason) {
  if (ok === _connected) return;
  _connected = ok;
  const banner = byId("disconnect-banner");
  const dot = byId("footerDot");
  if (!banner || !dot) return;
  if (ok) {
    banner.classList.remove("visible");
    dot.classList.remove("err");
  } else {
    byId("disconnectReason").textContent = reason || "unknown error";
    banner.classList.add("visible");
    dot.classList.add("err");
  }
}

// ── Fetch ─────────────────────────────────────────────────────────

async function getRuntimeSummary() {
  const response = await fetch(RUNTIME_SUMMARY_ENDPOINT, { method: "GET", cache: "no-store" });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}

// ── Render ────────────────────────────────────────────────────────

function renderStrategyAgentStatuses(latestStatuses) {
  const container = byId("strategyAgentRows");
  if (!container) return;
  if (!latestStatuses || typeof latestStatuses !== "object" || !Object.keys(latestStatuses).length) {
    container.innerHTML = "";
    return;
  }
  container.innerHTML = `<div class="card-section-label" style="margin-top:8px">Agent Statuses</div>` +
    Object.entries(latestStatuses).map(([name, status]) =>
      `<div class="agent-row"><span class="agent-name">${name}</span>${pillHTML(status, statusColor(String(status || "").toUpperCase()))}</div>`
    ).join("");
}

function renderWarnings(items) {
  const list = byId("warnings");
  if (!list) return;
  if (!Array.isArray(items) || !items.length) {
    list.innerHTML = `<li class="ok">No warnings reported.</li>`;
    return;
  }
  list.innerHTML = items.map(w => `<li>${safeStr(w)}</li>`).join("");
}

function render(summary) {
  const account       = summary.account                  || {};
  const market        = summary.market                   || {};
  const session       = summary.session                  || {};
  const decision      = summary.decision                 || {};
  const agents        = summary.strategy_agents          || {};
  const fastRsi       = summary.fast_rsi                 || {};
  const eventBus      = summary.event_bus                || {};
  const demoOms       = summary.demo_oms                 || {};
  const broker        = summary.broker_reconciliation    || {};
  const queue         = summary.demo_command_queue       || {};
  const safety        = summary.safety                   || {};
  const liveReadiness = summary.live_readiness           || {};
  const evidenceGrowth       = summary.evidence_growth        || {};
  const signalCertification  = summary.signal_certification   || {};
  const paperRiskAudit       = summary.paper_risk_audit       || {};
  const provenance           = summary.runtime_provenance     || {};
  const lifetime             = provenance.lifetime_counters   || {};
  const sessionCounters      = provenance.session_counters    || {};
  const assertion            = provenance.safety_assertion    || {};
  const evidenceIntegrity    = summary.evidence_integrity     || {};

  const symbol = summary.symbol || market.symbol;
  const sessionId = provenance.runtime_session_id;

  // ── Header ─────────────────────────────────────────────────────
  setText("hdrSymbol", symbol);
  setStatus("hdrHealth", summary.health);
  setText("hdrSession", shortId(sessionId));
  setText("hdrUptime", provenance.uptime_seconds != null
    ? `${Math.round(Number(provenance.uptime_seconds))}s`
    : "--");

  // ── Decision Strip ──────────────────────────────────────────────
  const action = decision.action || "--";
  setHTML("dsAction", pillHTML(action, statusColor(action)));

  const block = decision.top_blocking_reason || summary.top_blocks?.[0] || "--";
  setText("dsReason", block);

  const spreadPts = market.spread_points != null ? market.spread_points : "--";
  const maxSpr    = market.max_spread_threshold != null ? market.max_spread_threshold : "--";
  const spreadSt  = market.spread_status || "--";
  setHTML("dsSpread", `<span style="font-family:var(--mono)">${spreadPts} / ${maxSpr}</span> ${pillHTML(spreadSt, statusColor(spreadSt))}`);

  const overallSafe = assertion.overall_safe;
  setHTML("dsSafety", overallSafe === true
    ? pillHTML("SESSION SAFE", "good")
    : overallSafe === false
      ? pillHTML("UNSAFE", "danger")
      : pillHTML("UNKNOWN", "warn"));

  setText("dsNext", summary.next_expected_action || decision.next_expected_action || "--");

  // ── Market ──────────────────────────────────────────────────────
  setText("bid",          fixed(market.bid, 3));
  setText("ask",          fixed(market.ask, 3));
  setText("spread",       market.spread_points);
  setText("maxSpread",    market.max_spread_threshold);
  setStatus("spreadStatus", market.spread_status);
  setText("latestTick",   fmtTime(market.latest_tick_time));
  setText("latestCandle", fmtTime(market.latest_candle_time));

  // ── Account ─────────────────────────────────────────────────────
  setText("currency",    account.currency);
  setText("balance",     fixed(account.balance));
  setText("equity",      fixed(account.equity));
  setText("freeMargin",  fixed(account.free_margin));
  setText("marginLevel", account.margin_level);
  setText("accountHint", account.demo_real_hint);

  // ── Decision ────────────────────────────────────────────────────
  setStatus("decisionAction",     decision.action);
  setText("decisionDirection",    decision.direction);
  setText("decisionScore",        decision.score);
  setText("decisionConfidence",   decision.confidence);
  setText("decisionStrategy",     decision.strategy);
  setText("decisionSetup",        decision.setup_reason);
  setText("decisionTopBlock",     decision.top_blocking_reason || summary.top_blocks?.[0]);
  setText("decisionTopWarning",   decision.top_warning || summary.top_warnings?.[0]);
  setText("decisionAutonomy",     decision.autonomy_level);
  setText("decisionMode",         decision.mode);

  // ── Fast RSI ────────────────────────────────────────────────────
  setStatus("fastRsiStatus",       fastRsi.status);
  setText("fastRsiDirection",      fastRsi.direction);
  setText("fastRsiRsi",            fastRsi.rsi_current);
  setText("fastRsiSma",            fastRsi.rsi_sma_current);
  setText("fastRsiBuyExtreme",     fastRsi.buy_extreme_state);
  setText("fastRsiSellExtreme",    fastRsi.sell_extreme_state);
  setText("fastRsiRejections",     joinItems((fastRsi.rejection_reasons || []).map(r => r.message || r.code || r)));
  setText("fastRsiLastBar",        fmtTime(fastRsi.last_evaluated_bar));
  setText("fastRsiTrace",          fastRsi.decision_trace_available != null ? String(fastRsi.decision_trace_available) : "--");

  // ── Strategy Agents ─────────────────────────────────────────────
  setText("strategyAgentsRegistered",    agents.registered_count);
  setText("strategyAgentsEnabled",       agents.enabled_count);
  setText("strategyAgentsLatestStrategy",agents.latest_signal_strategy);
  setText("strategyAgentsSignal",        agents.latest_signal_direction);
  setExecLock("strategyAgentsPaperAllowed",  agents.paper_trade_creation_allowed);
  setExecLock("strategyAgentsOrderAllowed",  agents.order_request_creation_allowed);
  renderStrategyAgentStatuses(agents.latest_statuses);

  // ── Broker Reconciliation ───────────────────────────────────────
  setStatus("brokerReconStatus",    broker.status);
  setText("brokerReconPositions",   broker.broker_positions);
  setText("brokerReconOrders",      broker.broker_orders);
  setText("brokerReconMismatches",  broker.mismatches);
  setText("brokerReconWarnings",    broker.warnings);
  setSessionBool("brokerReconExposure", broker.unexpected_exposure);

  // ── Provenance ──────────────────────────────────────────────────
  setText("runtimeSessionId",     sessionId);
  setText("runtimeStartedAt",     fmtTime(provenance.started_at));
  setText("runtimeUptime",        provenance.uptime_seconds != null
    ? `${Math.round(Number(provenance.uptime_seconds))}s`
    : "--");
  setOverallSafe("runtimeSafetyAssertion", assertion.overall_safe);
  setText("latestProvenanceEvent",
    provenance.latest_provenance_event?.component ||
    provenance.latest_provenance_event?.runtime_session_id ||
    "--");

  setText("lifetimePaperTrades", lifetime.paper_trades);
  setText("sessionPaperTrades",  sessionCounters.paper_trades);
  setText("lifetimeCommands",    lifetime.commands);
  setText("sessionCommands",     sessionCounters.commands);
  setText("lifetimeOmsRequests", lifetime.oms_requests);
  setText("sessionOmsRequests",  sessionCounters.oms_requests);

  // ── Safety Locks ─────────────────────────────────────────────────
  setExecLock("safetyLiveExecution",   safety.live_execution_allowed);
  setExecLock("safetyLiveArming",      safety.live_arming_allowed);
  setExecLock("safetyDemoExecution",   safety.demo_execution_allowed);
  setExecLock("safetyCommandQueueing", safety.demo_command_queueing_allowed || safety.mt5_command_queueing_allowed);
  setSessionBool("safetyMt5Commands",  safety.mt5_commands_queued);
  setSessionBool("safetyBrokerOrder",  safety.broker_order_created);
  setSessionBool("safetyPaperTrade",   safety.paper_trade_created);
  setSessionBool("safetyOrderRequest", safety.order_request_creation_allowed);
  // read-only = true is GOOD
  setSafetyBool("safetyReadOnly", safety.read_only_dashboard, { invertSafe: false });
  setHTML("safetyReadOnly", safety.read_only_dashboard
    ? pillHTML("READ-ONLY", "good")
    : pillHTML("WRITABLE?", "danger"));

  // Session activity — false = green (nothing created this session)
  setSessionBool("sessionCreatedPaperTrade",  assertion.created_paper_trade);
  setSessionBool("sessionCreatedOrderRequest", assertion.created_order_request);
  setSessionBool("sessionQueuedMt5Command",    assertion.queued_mt5_command);
  setSessionBool("sessionCreatedBrokerOrder",  assertion.created_broker_order);
  setOverallSafe("sessionOverallSafe",         assertion.overall_safe);

  // ── Evidence Integrity ───────────────────────────────────────────
  setStatus("evidenceIntegrityStatus",   evidenceIntegrity.status);
  setStatus("evidencePaperLedger",       evidenceIntegrity.paper_ledger?.status);
  setStatus("evidenceJournalLedger",     evidenceIntegrity.journal_ledger?.status);
  setStatus("evidenceMonitorIntegrity",  evidenceIntegrity.evidence_monitor?.status);
  setStatus("evidenceLiveReadiness",     evidenceIntegrity.live_readiness?.status);
  setStatus("evidenceSignalCertification", evidenceIntegrity.signal_certification?.status);
  setText("evidenceStaleTempFiles",      evidenceIntegrity.stale_temp_file_count);
  setText("evidenceCorruptJsonFiles",    evidenceIntegrity.corrupt_json_file_count);
  setText("evidenceIntegrityNotes",      joinItems(evidenceIntegrity.notes || []));

  // ── Readiness ────────────────────────────────────────────────────
  setStatus("liveReadinessStatus",  liveReadiness.status);
  setStatus("evidenceGrowthStatus", evidenceGrowth.status);
  setStatus("signalCertStatus",     signalCertification.status);
  setStatus("paperRiskStatus",      paperRiskAudit.risk_status || paperRiskAudit.status);
  setText("session", session.name);

  // ── Demo OMS ─────────────────────────────────────────────────────
  setText("demoOmsMode",             demoOms.mode);
  setText("demoOmsIntentCount",      demoOms.intent_count);
  setText("demoOmsRequestCount",     demoOms.request_count);
  setStatus("demoOmsLatestRequest",  demoOms.latest_request_status);
  setExecLock("demoOmsDemoExecution",   demoOms.demo_execution_allowed);
  setExecLock("demoOmsLiveExecution",   demoOms.live_execution_allowed);
  setExecLock("demoOmsCommandQueueing", demoOms.command_queueing_allowed);

  // ── Demo Command Queue ───────────────────────────────────────────
  setText("demoCommandQueueMode",           queue.mode);
  setText("demoCommandQueuePreviews",       queue.preview_count);
  setText("demoCommandQueuePayloads",       queue.payload_count);
  setStatus("demoCommandQueueLatestPreview", queue.latest_preview_status);
  setStatus("demoCommandQueueLatestPayload", queue.latest_payload_status);
  setSessionBool("demoCommandQueueManualArm", queue.manual_demo_arm);
  setExecLock("demoCommandQueueDemoAllowed",  queue.demo_command_queueing_allowed);
  setExecLock("demoCommandQueueMt5Allowed",   queue.mt5_command_queueing_allowed);
  setText("demoCommandQueueMt5CommandId",    queue.mt5_command_id);
  setText("demoCommandQueueBrokerOrderId",   queue.broker_order_id);

  // ── Event Bus ────────────────────────────────────────────────────
  setText("eventBusCount",         eventBus.event_count);
  setText("eventBusSequence",      eventBus.last_sequence);
  setText("eventBusType",          eventBus.last_event_type);
  setText("eventBusStateAt",       fmtTime(eventBus.runtime_state_generated_at));
  setText("eventBusDecisionEvent",
    eventBus.latest_decision_event?.event_id ||
    eventBus.latest_decision_event?.payload?.action ||
    "--");

  // ── Why No Trade ─────────────────────────────────────────────────
  setText("whyPrimary",   summary.top_blocks?.[0]                       || decision.top_blocking_reason || "--");
  setText("whySecondary", joinItems((summary.top_blocks || []).slice(1)));
  setText("whyWarnings",  joinItems(summary.top_warnings || []));
  setText("whyNext",      summary.next_expected_action || decision.next_expected_action || "--");

  // ── Warnings List ────────────────────────────────────────────────
  renderWarnings(summary.top_warnings || []);

  // ── VPS Profile ──────────────────────────────────────────────────
  const vpsProfile = summary.vps_profile || summary.runtime_profile || "--";
  setText("vpsProfile",    vpsProfile);
  const host = summary.host || summary.bridge_host;
  const port = summary.port || summary.bridge_port;
  setText("vpsHostPort",   host && port ? `${host}:${port}` : (host || port || "--"));
  setText("vpsMt5Age",     summary.mt5_snapshot_age || account.snapshot_age || "--");
  setText("vpsTerminalId", summary.terminal_id || "--");
  setText("vpsSymbol",     symbol);

  // ── Footer ───────────────────────────────────────────────────────
  setText("updatedAt", `Updated ${new Date().toLocaleTimeString()} · polling every ${REFRESH_MS / 1000}s · read-only`);
}

// ── Poll loop ─────────────────────────────────────────────────────

async function refresh() {
  try {
    const summary = await getRuntimeSummary();
    setConnected(true);
    render(summary);
  } catch (err) {
    setConnected(false, err.message);
    const el = byId("updatedAt");
    if (el) el.textContent = `Runtime summary failed at ${new Date().toLocaleTimeString()} — ${err.message}`;
  }
}

refresh();
setInterval(refresh, REFRESH_MS);
