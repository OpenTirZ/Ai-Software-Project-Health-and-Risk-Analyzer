
from importlib import import_module

_dispatcher_exports = {
    "DeliveryDestination",
    "DeliveryDispatcher",
    "DeliveryStatus",
    "dispatch_report",
    "get_delivery_attempts",
    "record_delivery_attempt",
}

_scheduler_exports = {
    "ReportScheduler",
    "TriggerType",
    "generate_scheduled_report",
    "get_scheduler",
}

__all__ = list(_dispatcher_exports | _scheduler_exports)


def __getattr__(name):
    if name in _dispatcher_exports:
        module = import_module("Backend.reporting.delivery_dispatcher")
        return getattr(module, name)

    if name in _scheduler_exports:
        module = import_module("Backend.reporting.scheduler")
        return getattr(module, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
