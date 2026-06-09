from __future__ import annotations

from typing import Iterable

from .config import EventBusConfig
from .models import AurixEvent
from .store import EventBusStore


class AurixEventBus:
    def __init__(self, data_dir: str = "data", config: EventBusConfig | None = None):
        self.config = config or EventBusConfig()
        self.store = EventBusStore(data_dir, self.config)

    def publish_event(self, event: AurixEvent | dict) -> dict:
        if not self.config.enabled:
            raise RuntimeError("event bus is disabled")
        parsed = event if isinstance(event, AurixEvent) else AurixEvent(**event)
        parsed.safety.live_execution_allowed = False
        parsed.safety.live_arming_allowed = False
        parsed.safety.command_queueing_allowed = False
        parsed.safety.mt5_commands_queued = False
        parsed.safety.broker_order_created = False
        parsed.safety.ea_settings_modified = False
        parsed.safety.external_llm_used = False
        parsed.safety.strategy_config_mutated = False
        return self.store.append_event(parsed).model_dump(mode="json")

    def publish_many(self, events: Iterable[AurixEvent | dict]) -> list[dict]:
        published: list[dict] = []
        for event in events:
            published.append(self.publish_event(event))
        return published

    def load_recent_events(self, limit: int = 20) -> list[dict]:
        return self.store.recent_events(limit)

    def load_events_by_type(self, event_type: str, limit: int = 20) -> list[dict]:
        return self.store.events_by_type(event_type, limit)

    def load_events_by_correlation_id(self, correlation_id: str) -> list[dict]:
        return self.store.events_by_correlation_id(correlation_id)

    def get_latest_status(self) -> dict:
        return self.store.status()

    def get_latest_state(self) -> dict:
        return self.store.state_snapshot()

    def reset_event_bus(self) -> dict:
        return self.store.reset()
