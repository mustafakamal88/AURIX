"use strict";

const REFRESH_MS = 4000;
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
  const GOOD_SET = new Set(["OK", "CLEAN", "SAFE", "HEALTHY", "PASS", "PASSED", "ACTIVE", "CERTIFIED", "VALID", "TRUE", "ENABLED", "SUCCESS", "READY", "READ_ONLY", "CANNOT_CREATE_COMMANDS", "RUNNING", "ACTIONABLE"]);
  const WARN_SET = new Set(["WARNING", "WARN", "DEGRADED", "STALE", "PARTIAL", "COLLECTING", "PENDING", "NO_SETUP", "LOW_CONFIDENCE", "WAITING_FOR_NEXT_CANDLE", "WAITING_FOR_DATA", "NEUTRAL", "NONE"]);
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

// Overall runtime-session safe: true = green, false = danger
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
  const url = new URL(RUNTIME_SUMMARY_ENDPOINT, window.location.origin);
  const response = await fetch(url.toString(), { method: "GET", cache: "no-store", credentials: "same-origin" });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}

async function getDashboardSession() {
  const response = await fetch("/dashboard/session", { method: "GET", cache: "no-store", credentials: "same-origin" });
  if (!response.ok) return null;
  return response.json();
}

async function logoutDashboard() {
  await fetch("/dashboard/logout", { method: "POST", credentials: "same-origin" });
  window.location.assign("/dashboard/login");
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
  const demoBroker    = summary.demo_broker_execution    || {};
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
  const runtimeEnvironment   = summary.runtime_environment    || {};
  const quickValidation      = summary.quick_validation       || {};
  const pipeline             = summary.strategy_pipeline      || {};
  const cockpit              = summary.broker_execution_cockpit || {};
  const quickValidationSafety = quickValidation.safety         || {};
  const quickValidationSummary = quickValidation.summary       || {};
  const demoBrokerConfig     = demoBroker.config || {};
  const demoAccount          = demoBroker.demo_account_verification || {};
  const demoGate             = demoBroker.latest_gate_decision || {};
  const dailyRisk            = demoBroker.daily_risk_guard || {};
  const latestDemoCommand    = demoBroker.latest_command || {};
  const latestDemoResult     = demoBroker.latest_execution_result || {};

  const symbol = summary.symbol || market.symbol;
  const tradingSession = session.trading_session || {};
  const sessionId = provenance.runtime_session_id;
  const railwayBrokerEnabled = cockpit.railway_broker_execution === true;
  const eaBrokerEnabled = cockpit.ea_broker_execution === true;
  const matched = cockpit.broker_execution_matched;

  // ── Header ─────────────────────────────────────────────────────
  setText("hdrSymbol", symbol);
  setStatus("hdrHealth", summary.health);
  setText("hdrHealthReason", summary.health_reason);
  setStatus("hdrRuntimeSafety", assertion.overall_safe === true ? "SAFE" : assertion.overall_safe === false ? "UNSAFE" : summary.health === "STALE" ? "STALE" : "UNKNOWN", assertion.overall_safe === true ? "good" : assertion.overall_safe === false ? "danger" : "warn");
  setStatus("hdrTradingSession", tradingSession.name || "UNKNOWN");
  setText("hdrSession", shortId(sessionId));
  setText("hdrUptime", provenance.uptime_seconds != null
    ? `${Math.round(Number(provenance.uptime_seconds))}s`
    : "--");
  setStatus("bannerBrokerExecution", railwayBrokerEnabled ? "BROKER EXECUTION ENABLED" : "BROKER EXECUTION DISABLED", railwayBrokerEnabled ? "danger" : "good");
  setStatus("bannerEaExecution", eaBrokerEnabled ? "EA EXECUTION ENABLED" : "EA EXECUTION DISABLED", eaBrokerEnabled ? "danger" : "good");
  setStatus("bannerExecutionMatch", matched === true ? "EXECUTION STATE MATCHED" : matched === false ? "EXECUTION STATE MISMATCH" : "EXECUTION STATE UNKNOWN", matched === true ? "good" : matched === false ? "danger" : "warn");
  setStatus("bannerReadOnly", "READ-ONLY DASHBOARD", "good");
  setStatus("bannerNoCommands", "NO COMMANDS FROM DASHBOARD", "good");

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
    ? pillHTML("Runtime Safety: SAFE", "good")
    : overallSafe === false
      ? pillHTML("Runtime Safety: UNSAFE", "danger")
      : pillHTML(summary.health === "STALE" ? "Runtime Safety: STALE" : "Runtime Safety: UNKNOWN", "warn"));

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

  // ── Broker Execution Cockpit ────────────────────────────────────
  setStatus("cockpitRailwayExecution", railwayBrokerEnabled ? "ENABLED" : "DISABLED", railwayBrokerEnabled ? "danger" : "good");
  setStatus("cockpitEaExecution", eaBrokerEnabled ? "ENABLED" : "DISABLED", eaBrokerEnabled ? "danger" : "good");
  setStatus("cockpitExecutionMatch", matched === true ? "MATCHED" : matched === false ? "MISMATCH" : "UNKNOWN", matched === true ? "good" : matched === false ? "danger" : "warn");
  setText("cockpitTerminalId", cockpit.terminal_id || runtimeEnvironment.mt5_terminal_id);
  setText("cockpitSymbol", cockpit.symbol || symbol);
  setText("cockpitPositions", cockpit.positions_count);
  setStatus("cockpitCommandState", cockpit.latest_command_state || "NO_COMMAND");
  setText("cockpitCommandReason", cockpit.latest_command_reason);
  setText("cockpitPrimaryBlock", cockpit.latest_primary_block);

  setStatus("gateQueueState", cockpit.aurix_queue_state);
  setStatus("gateSpreadState", cockpit.spread_gate_state);
  setText("gateEngineMaxSpread", cockpit.engine_max_spread != null ? `${cockpit.engine_max_spread} points` : "--");
  setText("gateCurrentSpread", cockpit.current_spread);
  setText("gateRiskModel", cockpit.risk_model ? `${cockpit.risk_model.risk_per_trade_percent ?? "--"}% per trade / ${cockpit.risk_model.daily_risk_limit_percent ?? "--"}% daily${cockpit.risk_model.risk_amount != null ? ` / risk ${cockpit.risk_model.risk_amount}` : ""}` : "--");
  setText("gateSelectedStrategy", cockpit.selected_strategy);
  setStatus("gateLatestSignalStatus", cockpit.latest_signal_status);

  setStatus("validationQuickStatus", cockpit.quick_validation_status || quickValidation.status || "NOT_RUN");
  setText("validationQuickCounts", `${cockpit.quick_validation_pass_count ?? quickValidationSummary.pass_count ?? 0} / ${cockpit.quick_validation_fail_count ?? quickValidationSummary.fail_count ?? 0} / ${cockpit.quick_validation_warning_count ?? quickValidationSummary.warning_count ?? 0}`);
  setStatus("validationEvidenceStatus", cockpit.evidence_status || evidenceGrowth.status);
  setStatus("validationReadinessStatus", cockpit.live_readiness_status || liveReadiness.status);
  setStatus("validationArmingAllowed", cockpit.live_readiness_arming_allowed ? "ALLOWED" : "BLOCKED", cockpit.live_readiness_arming_allowed ? "danger" : "good");
  setStatus("validationExecutionAllowed", cockpit.live_readiness_execution_allowed ? "ALLOWED" : "BLOCKED", cockpit.live_readiness_execution_allowed ? "danger" : "good");
  setText("validationBlockCount", (liveReadiness.blocking_reasons || []).length + (quickValidation.blocking_reasons || []).length);

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
  setText("fastRsiBuyThreshold",   fastRsi.buy_extreme_threshold);
  setText("fastRsiSellThreshold",  fastRsi.sell_extreme_threshold);
  setText("fastRsiBuyExtreme",     fastRsi.buy_extreme_state);
  setText("fastRsiSellExtreme",    fastRsi.sell_extreme_state);
  setText("fastRsiRejections",     joinItems((fastRsi.rejection_reasons || []).map(r => r.message || r.code || r)));
  setText("fastRsiLastBar",        fmtTime(fastRsi.last_evaluated_bar));
  setText("fastRsiEvalAge",        fastRsi.last_evaluation_age_seconds != null ? `${Math.round(Number(fastRsi.last_evaluation_age_seconds))}s` : "--");
  setText("fastRsiTrace",          fastRsi.decision_trace_available != null ? String(fastRsi.decision_trace_available) : "--");
  setStatus("fastRsiLatestResult", fastRsi.latest_result);
  setStatus("fastRsiLatestRejection", fastRsi.latest_rejection_reason);

  // ── Strategy Pipeline ───────────────────────────────────────────
  setStatus("pipelineMarketFresh", pipeline.market_data_fresh === true ? "TRUE" : "FALSE", pipeline.market_data_fresh === true ? "good" : "danger");
  setStatus("pipelineDecisionAlive", pipeline.decision_loop_alive === true ? "TRUE" : "FALSE", pipeline.decision_loop_alive === true ? "good" : "danger");
  setStatus("pipelineRegistryLoaded", pipeline.strategy_registry_loaded === true ? "TRUE" : "FALSE", pipeline.strategy_registry_loaded === true ? "good" : "danger");
  setText("pipelineRegistered", pipeline.registered_strategy_count);
  setText("pipelineEnabled", pipeline.enabled_strategy_count);
  setText("pipelineEvaluations", pipeline.evaluations_this_session);
  setText("pipelineEvalAge", pipeline.latest_evaluation_age_seconds != null ? `${Math.round(Number(pipeline.latest_evaluation_age_seconds))}s` : "--");
  setText("pipelineLastStrategy", pipeline.latest_strategy_name || "none");
  setStatus("pipelineLastResult", pipeline.latest_result);
  setStatus("pipelineLastDirection", pipeline.latest_direction_candidate);
  setText("pipelineLastConfidence", pipeline.latest_confidence);
  setStatus("pipelineLastRejection", pipeline.latest_rejection_reason);
  setText("pipelineLastError", pipeline.latest_error);

  // ── Strategy Agents ─────────────────────────────────────────────
  setText("strategyAgentsRegistered",    agents.registered_count);
  setText("strategyAgentsEnabled",       agents.enabled_count);
  setText("strategyAgentsLatestStrategy",agents.latest_signal_strategy || pipeline.latest_strategy_name || "none");
  setText("strategyAgentsSignal",        agents.latest_signal_direction || pipeline.latest_direction_candidate || "NONE");
  setStatus("strategyAgentsLatestResult", pipeline.latest_result || "UNKNOWN");
  setStatus("strategyAgentsLatestRejection", pipeline.latest_rejection_reason || "--");
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
  setStatus("runtimeTradingSession", tradingSession.name || "UNKNOWN");
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
  setStatus("safetyBrokerOrderPermission", cockpit.broker_order_permission || (safety.live_execution_allowed ? "ALLOWED" : "BLOCKED"), safety.live_execution_allowed ? "danger" : "good");
  setText("safetyBrokerOrderReason", cockpit.broker_order_permission_reason || cockpit.latest_primary_block || "--");
  setExecLock("safetyLiveArming",      safety.live_arming_allowed);
  setStatus("safetyDemoExecution",   cockpit.legacy_gate_status || "IGNORED / RETIRED", "neutral");
  setStatus("safetyCommandQueueing", cockpit.aurix_queue_state || demoBroker.queue_state || demoGate.queue_state || "--");
  setText("safetyQueueReason", cockpit.aurix_queue_reason || "--");
  setSessionBool("safetyMt5Commands",  safety.mt5_commands_queued);
  setSessionBool("safetyBrokerOrder",  safety.broker_order_created);
  setSessionBool("safetyPaperTrade",   safety.paper_trade_created);
  setSessionBool("safetyOrderRequest", safety.order_request_creation_allowed);
  // read-only = true is GOOD
  setSafetyBool("safetyReadOnly", safety.read_only_dashboard, { invertSafe: false });
  setHTML("safetyReadOnly", safety.read_only_dashboard
    ? pillHTML(cockpit.dashboard_order_capability || "READ_ONLY / CANNOT_CREATE_COMMANDS", "good")
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

  // ── Quick Validation ─────────────────────────────────────────────
  setStatus("quickValidationStatus", quickValidation.status || "NOT_RUN");
  setText("quickValidationCounts", `${quickValidationSummary.pass_count ?? 0} / ${quickValidationSummary.fail_count ?? 0} / ${quickValidationSummary.warning_count ?? 0}`);
  setStatus("quickValidationPaperOnly", quickValidationSafety.paper_only === true ? "TRUE" : "--");
  setStatus("quickValidationBrokerExecution", quickValidationSafety.broker_execution_enabled ? "ENABLED" : "DISABLED");
  setStatus("quickValidationMt5Commands", quickValidationSafety.mt5_commands_queued ? "QUEUED" : "NONE");
  setText("quickValidationRecommendation", Array.isArray(quickValidation.recommendations) ? quickValidation.recommendations[0] : "--");

  // ── Demo OMS ─────────────────────────────────────────────────────
  setText("demoOmsMode",             demoOms.mode);
  setText("demoOmsIntentCount",      demoOms.intent_count);
  setText("demoOmsRequestCount",     demoOms.request_count);
  setStatus("demoOmsLatestRequest",  demoOms.latest_request_status);
  setExecLock("demoOmsDemoExecution",   demoOms.demo_execution_allowed);
  setExecLock("demoOmsLiveExecution",   demoOms.live_execution_allowed);
  setStatus("demoOmsCommandQueueing", demoOms.broker_execution_enabled ? "ENABLED" : "DISABLED");

  // ── Demo Command Queue ───────────────────────────────────────────
  setText("demoCommandQueueMode",           queue.mode);
  setText("demoCommandQueuePreviews",       queue.preview_count);
  setText("demoCommandQueuePayloads",       queue.payload_count);
  setStatus("demoCommandQueueLatestPreview", queue.latest_preview_status);
  setStatus("demoCommandQueueLatestPayload", queue.latest_payload_status);
  setStatus("demoCommandQueueManualArm", queue.broker_execution_enabled ? "ENABLED" : "DISABLED");
  setStatus("demoCommandQueueDemoAllowed", queue.aurix_queue_state || demoBroker.queue_state || demoGate.queue_state || "--");
  setStatus("demoCommandQueueMt5Allowed", queue.mt5_delivery_state || latestDemoCommand.status || "NO_COMMAND");
  setText("demoCommandQueueMt5CommandId",    queue.mt5_command_id);
  setText("demoCommandQueueBrokerOrderId",   queue.broker_order_id);

  // ── Demo Broker Execution ────────────────────────────────────────
  setStatus("demoBrokerEnabled", demoBroker.broker_execution || (demoBrokerConfig.broker_execution_enabled ? "ENABLED" : "DISABLED"));
  setStatus("demoBrokerQueueEnabled", demoBroker.queue_state || demoGate.queue_state || "--");
  setStatus("demoBrokerLiveLocked", demoBroker.spread_gate || demoGate.spread_gate || "--");
  setText("demoBrokerOnePosition", demoBroker.engine_max_spread_points != null ? `${demoBroker.engine_max_spread_points} points` : "--");
  setStatus("demoBrokerGate", dailyRisk.status || (demoGate.daily_risk_guard ? demoGate.daily_risk_guard.status : "--"));
  setStatus("demoBrokerSignalGate", cockpit.signal_gate_state || (demoGate.allowed ? "PASS" : (demoGate.primary_block === "no actionable signal" || demoGate.primary_block === "signal direction missing" ? "BLOCKED" : "--")));
  setText("demoBrokerReason", demoBroker.latest_gate_block || demoGate.primary_block || demoGate.reason);
  setText("demoBrokerSelectedStrategy", cockpit.selected_strategy || demoBroker.selected_strategy);
  setText("demoBrokerSignalDirection", cockpit.latest_signal_direction || demoBroker.latest_signal_direction);
  setStatus("demoBrokerSignalStatus", cockpit.latest_signal_status || demoBroker.latest_signal_status);
  setOverallSafe("demoAccountVerified", demoAccount.demo_account_verified);
  setText("demoAccountReason", demoAccount.demo_account_reason);
  setText("demoAccountServer", demoAccount.account_server);
  setText("demoAccountLogin", demoAccount.account_login_masked);
  setText("demoAccountCurrency", demoAccount.account_currency);
  setStatus("dailyRiskStatus", dailyRisk.status);
  setText("dailyRiskLoss", dailyRisk.equity_loss);
  setText("dailyRiskDrawdown", dailyRisk.drawdown_percent);
  setText("latestMt5Command", latestDemoCommand.command_id);
  setStatus("latestMt5CommandStatus", latestDemoCommand.status);
  setStatus("latestMt5ExecutionResult", latestDemoResult.status);

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
  setStatus("whySignalGate", cockpit.signal_gate_state || "--");
  setText("whyQueue", cockpit.aurix_queue_state ? `${cockpit.aurix_queue_state}${cockpit.aurix_queue_reason ? ` because ${cockpit.aurix_queue_reason}` : ""}` : "--");
  setText("whyWarnings",  joinItems(summary.top_warnings || []));
  setText("whyNext",      summary.next_expected_action || decision.next_expected_action || "--");

  // ── Warnings List ────────────────────────────────────────────────
  renderWarnings([...(summary.top_warnings || []), ...(quickValidation.warnings || [])]);

  // ── VPS Profile ──────────────────────────────────────────────────
  const vpsProfile = runtimeEnvironment.runtime_profile || summary.vps_profile || summary.runtime_profile || "--";
  setText("vpsProfile",    vpsProfile);
  const host = summary.host || summary.bridge_host;
  const port = summary.port || summary.bridge_port;
  setText("vpsHostPort",   host && port ? `${host}:${port}` : (host || port || "--"));
  setText("vpsPublicBaseUrl", runtimeEnvironment.public_base_url);
  setStatus("vpsRemoteAuth", runtimeEnvironment.remote_auth_required ? "REQUIRED" : "LOCAL_ONLY", runtimeEnvironment.remote_auth_required ? "warn" : "good");
  setText("vpsDataDir", runtimeEnvironment.data_dir);
  setText("vpsLogDir", runtimeEnvironment.log_dir);
  setStatus("vpsRailwayVolume", runtimeEnvironment.railway_volume_detected);
  setText("vpsMt5Age",     market.snapshot_age_seconds || summary.mt5_snapshot_age || account.snapshot_age || "--");
  setText("vpsTerminalId", runtimeEnvironment.mt5_terminal_id || summary.terminal_id || "--");
  setText("vpsSymbol",     symbol);
  setOverallSafe("vpsDashboardReadOnly", runtimeEnvironment.dashboard_read_only !== false);
  setStatus("vpsLiveLocked", runtimeEnvironment.broker_execution_enabled ? "ENABLED" : "DISABLED");
  setText("vpsDemoDisabled", demoBroker.strategy_engine);
  setText("vpsCommandDisabled", demoBroker.selected_strategy || agents.latest_strategy);

  // ── Footer ───────────────────────────────────────────────────────
  setText("updatedAt", `Updated ${new Date().toLocaleTimeString()} · polling every ${REFRESH_MS / 1000}s · read-only`);
}

// ── Poll loop ─────────────────────────────────────────────────────

async function refresh() {
  try {
    const session = await getDashboardSession();
    if (session && session.authenticated) {
      setStatus("dashboardSessionStatus", "Authenticated dashboard session", "good");
    }
    const summary = await getRuntimeSummary();
    setConnected(true);
    render(summary);
  } catch (err) {
    setConnected(false, err.message);
    const el = byId("updatedAt");
    if (el) el.textContent = `Runtime summary failed at ${new Date().toLocaleTimeString()} — ${err.message}`;
  }
}

const logoutButton = byId("dashboardLogout");
if (logoutButton) logoutButton.addEventListener("click", logoutDashboard);
refresh();
setInterval(refresh, REFRESH_MS);
