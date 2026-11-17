"""
Reporting and delivery scheduling package.
Provides recurring schedule triggers and multi-channel report dispatching.
"""

from Backend.reporting.delivery_dispatcher import (
    DeliveryDestination,
    DeliveryDispatcher,
    DeliveryStatus,
    dispatch_report,
    get_delivery_attempts,
    record_delivery_attempt,
)
from Backend.reporting.scheduler import (
    ReportScheduler,
    TriggerType,
    generate_scheduled_report,
    get_scheduler,
)

__all__ = [
    "DeliveryDestination",
    "DeliveryDispatcher",
    "DeliveryStatus",
    "dispatch_report",
    "record_delivery_attempt",
    "get_delivery_attempts",
    "ReportScheduler",
    "TriggerType",
    "generate_scheduled_report",
    "get_scheduler",
]
