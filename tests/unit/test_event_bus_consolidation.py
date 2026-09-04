import warnings
import pytest
import logging
from core.event_bus import EventBus as CoreEventBus, Event, Events


def test_core_event_bus_singleton_and_dispatch():
    """Verify that CoreEventBus provides a thread-safe singleton and delivers typed events."""
    bus1 = CoreEventBus.get_instance()
    bus2 = CoreEventBus.get_instance()
    assert bus1 is bus2

    received_events = []

    def handler(evt: Event):
        received_events.append(evt)

    bus1.subscribe(Events.CONFIRMATION_REQUIRED, handler)
    bus1.publish(Events.CONFIRMATION_REQUIRED, ticket_id="tkt_abc123", risk="HIGH")

    assert len(received_events) == 1
    assert received_events[0].name == Events.CONFIRMATION_REQUIRED
    assert received_events[0].payload.get("ticket_id") == "tkt_abc123"
    assert received_events[0].payload.get("risk") == "HIGH"

    # Cleanup
    bus1.unsubscribe(Events.CONFIRMATION_REQUIRED, handler)
    bus1.publish(Events.CONFIRMATION_REQUIRED, ticket_id="tkt_def456")
    assert len(received_events) == 1


def test_brain_aca_event_bus_deprecation_and_delegation(caplog):
    """Verify that importing and using brain.aca.event_bus issues deprecation warning and delegates cleanly."""
    with warnings.catch_warnings(record=True) as recorded_warnings:
        warnings.simplefilter("always")
        import importlib
        import brain.aca.event_bus as aca_bus_module
        importlib.reload(aca_bus_module)

        dep_warnings = [w for w in recorded_warnings if issubclass(w.category, DeprecationWarning)]
        assert any("brain.aca.event_bus is deprecated" in str(w.message) for w in dep_warnings)

    with caplog.at_level(logging.WARNING):
        aca_bus = aca_bus_module.EventBus()

    assert any("[DEPRECATION] brain.aca.event_bus.EventBus is deprecated" in rec.message for rec in caplog.records)

    received_payloads = []

    def legacy_handler(data: dict):
        received_payloads.append(data)

    aca_bus.subscribe("test.event", legacy_handler)
    aca_bus.publish("test.event", {"status": "ok"})

    assert len(received_payloads) == 1
    assert received_payloads[0] == {"status": "ok"}

    aca_bus.unsubscribe("test.event", legacy_handler)
    aca_bus.publish("test.event", {"status": "second"})
    assert len(received_payloads) == 1
