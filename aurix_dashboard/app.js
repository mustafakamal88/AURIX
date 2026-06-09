const REFRESH_MS = 5000;
const RUNTIME_SUMMARY_ENDPOINT = "/dashboard/runtime-summary";

function byId(id) {
  return document.getElementById(id);
}

function text(id, value) {
  const node = byId(id);
  if (!node) return;
  node.textContent = value === undefined || value === null || value === "" ? "--" : String(value);
}

function boolText(value) {
  return value ? "true" : "false";
}

function fixed(value, digits = 2) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(digits) : "--";
}

function joinItems(items) {
  return Array.isArray(items) && items.length ? items.map(String).join("; ") : "--";
}

function renderWarnings(items) {
  const list = byId("warnings");
  if (!list) return;
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

async function getRuntimeSummary() {
  const response = await fetch(RUNTIME_SUMMARY_ENDPOINT, { method: "GET", cache: "no-store" });
  if (!response.ok) {
    throw new Error(`${RUNTIME_SUMMARY_ENDPOINT} returned ${response.status}`);
  }
  return response.json();
}

function render(summary) {
  const account = summary.account || {};
  const market = summary.market || {};
  const session = summary.session || {};
  const decision = summary.decision || {};
  const agents = summary.strategy_agents || {};
  const fastRsi = summary.fast_rsi || {};
  const eventBus = summary.event_bus || {};
  const demoOms = summary.demo_oms || {};
  const broker = summary.broker_reconciliation || {};
  const queue = summary.demo_command_queue || {};
  const safety = summary.safety || {};
  const liveReadiness = summary.live_readiness || {};
  const evidenceGrowth = summary.evidence_growth || {};
  const signalCertification = summary.signal_certification || {};
  const paperRiskAudit = summary.paper_risk_audit || {};
  const provenance = summary.runtime_provenance || {};
  const lifetime = provenance.lifetime_counters || {};
  const sessionCounters = provenance.session_counters || {};
  const assertion = provenance.safety_assertion || {};
  const evidenceIntegrity = summary.evidence_integrity || {};

  text("service", "aurix-mac-wine-bridge");
  text("mode", decision.mode || queue.mode || demoOms.mode);
  text("symbol", summary.symbol || market.symbol);
  text("marketSymbol", summary.symbol || market.symbol);
  text("health", summary.health);
  text("liveTrading", safety.live_execution_allowed ? "ENABLED" : "DISABLED");
  text("paperOnly", boolText(!safety.real_account_execution_allowed));

  text("decisionAction", decision.action);
  text("decisionDirection", decision.direction);
  text("decisionScore", decision.score);
  text("decisionConfidence", decision.confidence);
  text("decisionStrategy", decision.strategy);
  text("decisionSetup", decision.setup_reason);
  text("decisionTopBlock", decision.top_blocking_reason || summary.top_blocks?.[0]);
  text("decisionTopWarning", decision.top_warning || summary.top_warnings?.[0]);
  text("decisionAutonomy", decision.autonomy_level);
  text("decisionMode", decision.mode);

  text("bid", fixed(market.bid, 3));
  text("ask", fixed(market.ask, 3));
  text("spread", market.spread_points);
  text("maxSpread", market.max_spread_threshold);
  text("spreadStatus", market.spread_status);
  text("latestTick", market.latest_tick_time);
  text("latestCandle", market.latest_candle_time);
  text("marketQuality", market.spread_status);

  text("currency", account.currency);
  text("balance", fixed(account.balance));
  text("equity", fixed(account.equity));
  text("freeMargin", fixed(account.free_margin));
  text("marginLevel", account.margin_level);
  text("accountHint", account.demo_real_hint);

  text("session", session.name);

  text("fastRsiStatus", fastRsi.status);
  text("fastRsiDirection", fastRsi.direction);
  text("fastRsiRsi", fastRsi.rsi_current);
  text("fastRsiSma", fastRsi.rsi_sma_current);
  text("fastRsiBuyExtreme", fastRsi.buy_extreme_state);
  text("fastRsiSellExtreme", fastRsi.sell_extreme_state);
  text("fastRsiRejections", joinItems((fastRsi.rejection_reasons || []).map((item) => item.message || item.code || item)));
  text("fastRsiLastBar", fastRsi.last_evaluated_bar);
  text("fastRsiTrace", boolText(fastRsi.decision_trace_available));

  text("strategyAgentsRegistered", agents.registered_count);
  text("strategyAgentsEnabled", agents.enabled_count);
  text("strategyAgentsStatuses", JSON.stringify(agents.latest_statuses || {}));
  text("strategyAgentsLatestStrategy", agents.latest_signal_strategy);
  text("strategyAgentsSignal", agents.latest_signal_direction);
  text("strategyAgentsPaperAllowed", boolText(agents.paper_trade_creation_allowed));
  text("strategyAgentsOrderAllowed", boolText(agents.order_request_creation_allowed));

  text("brokerReconStatus", broker.status);
  text("brokerReconPositions", broker.broker_positions);
  text("brokerReconOrders", broker.broker_orders);
  text("brokerReconMismatches", broker.mismatches);
  text("brokerReconWarnings", broker.warnings);
  text("brokerReconExposure", boolText(broker.unexpected_exposure));

  text("demoOmsMode", demoOms.mode);
  text("demoOmsIntentCount", demoOms.intent_count);
  text("demoOmsRequestCount", demoOms.request_count);
  text("demoOmsLatestRequest", demoOms.latest_request_status);
  text("demoOmsDemoExecution", boolText(demoOms.demo_execution_allowed));
  text("demoOmsLiveExecution", boolText(demoOms.live_execution_allowed));
  text("demoOmsCommandQueueing", boolText(demoOms.command_queueing_allowed));

  text("demoCommandQueueMode", queue.mode);
  text("demoCommandQueuePreviews", queue.preview_count);
  text("demoCommandQueuePayloads", queue.payload_count);
  text("demoCommandQueueLatestPreview", queue.latest_preview_status);
  text("demoCommandQueueLatestPayload", queue.latest_payload_status);
  text("demoCommandQueueManualArm", boolText(queue.manual_demo_arm));
  text("demoCommandQueueDemoAllowed", boolText(queue.demo_command_queueing_allowed));
  text("demoCommandQueueMt5Allowed", boolText(queue.mt5_command_queueing_allowed));
  text("demoCommandQueueMt5CommandId", queue.mt5_command_id);
  text("demoCommandQueueBrokerOrderId", queue.broker_order_id);

  text("eventBusCount", eventBus.event_count);
  text("eventBusSequence", eventBus.last_sequence);
  text("eventBusType", eventBus.last_event_type);
  text("eventBusStateAt", eventBus.runtime_state_generated_at);
  text("eventBusDecisionEvent", eventBus.latest_decision_event?.event_id || eventBus.latest_decision_event?.payload?.action);

  text("eaAllowLiveTrading", "false/unknown");
  text("safetyLiveExecution", boolText(safety.live_execution_allowed));
  text("safetyLiveArming", boolText(safety.live_arming_allowed));
  text("safetyDemoExecution", boolText(safety.demo_execution_allowed));
  text("safetyCommandQueueing", boolText(safety.demo_command_queueing_allowed || safety.mt5_command_queueing_allowed));
  text("safetyBrokerOrder", boolText(safety.broker_order_created));
  text("safetyMt5Commands", boolText(safety.mt5_commands_queued));
  text("safetyPaperTrade", boolText(safety.paper_trade_created));
  text("safetyOrderRequest", boolText(safety.order_request_creation_allowed));
  text("sessionCreatedPaperTrade", boolText(assertion.created_paper_trade));
  text("sessionCreatedOrderRequest", boolText(assertion.created_order_request));
  text("sessionQueuedMt5Command", boolText(assertion.queued_mt5_command));
  text("sessionCreatedBrokerOrder", boolText(assertion.created_broker_order));
  text("sessionOverallSafe", boolText(assertion.overall_safe));
  text("safetyReadOnly", boolText(safety.read_only_dashboard));

  text("runtimeSessionId", provenance.runtime_session_id);
  text("runtimeStartedAt", provenance.started_at);
  text("runtimeUptime", provenance.uptime_seconds === undefined || provenance.uptime_seconds === null ? "--" : `${Math.round(Number(provenance.uptime_seconds))}s`);
  text("lifetimePaperTrades", lifetime.paper_trades);
  text("sessionPaperTrades", sessionCounters.paper_trades);
  text("lifetimeCommands", lifetime.commands);
  text("sessionCommands", sessionCounters.commands);
  text("lifetimeOmsRequests", lifetime.oms_requests);
  text("sessionOmsRequests", sessionCounters.oms_requests);
  text("runtimeSafetyAssertion", boolText(assertion.overall_safe));
  text("latestProvenanceEvent", provenance.latest_provenance_event?.component || provenance.latest_provenance_event?.runtime_session_id);

  text("evidenceIntegrityStatus", evidenceIntegrity.status);
  text("evidencePaperLedger", evidenceIntegrity.paper_ledger?.status);
  text("evidenceJournalLedger", evidenceIntegrity.journal_ledger?.status);
  text("evidenceMonitorIntegrity", evidenceIntegrity.evidence_monitor?.status);
  text("evidenceLiveReadiness", evidenceIntegrity.live_readiness?.status);
  text("evidenceSignalCertification", evidenceIntegrity.signal_certification?.status);
  text("evidenceStaleTempFiles", evidenceIntegrity.stale_temp_file_count);
  text("evidenceCorruptJsonFiles", evidenceIntegrity.corrupt_json_file_count);
  text("evidenceIntegrityNotes", joinItems(evidenceIntegrity.notes || []));

  text("whyPrimary", summary.top_blocks?.[0]);
  text("whySecondary", joinItems((summary.top_blocks || []).slice(1)));
  text("whyWarnings", joinItems(summary.top_warnings || []));
  text("whyNext", summary.next_expected_action);

  text("liveReadinessStatus", liveReadiness.status);
  text("evidenceGrowthStatus", evidenceGrowth.status);
  text("signalCertStatus", signalCertification.status);
  text("paperRiskStatus", paperRiskAudit.risk_status || paperRiskAudit.status);

  renderWarnings(summary.top_warnings || []);
  text("updatedAt", `Last refreshed ${new Date().toLocaleTimeString()}. Dashboard is read-only.`);
}

async function refresh() {
  try {
    render(await getRuntimeSummary());
  } catch (error) {
    text("health", "ERROR");
    text("updatedAt", `Runtime summary failed: ${error.message}`);
  }
}

refresh();
setInterval(refresh, REFRESH_MS);
