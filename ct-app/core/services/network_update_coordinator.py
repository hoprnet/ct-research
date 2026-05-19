from collections.abc import Callable

from prometheus_client import Counter, Gauge
from ..constants.labels import NetworkUpdateSource
from .base_drain_coordinator import BaseDrainCoordinator

NETWORK_UPDATE_REQUESTS = Counter(
    "ct_network_update_requests_total",
    "Network update refresh requests",
    ["source"],
)
NETWORK_UPDATE_DRAINS = Counter(
    "ct_network_update_drains_total",
    "Network update drain executions",
)
NETWORK_UPDATE_PENDING = Gauge(
    "ct_network_update_pending",
    "Whether a network update refresh is pending",
)


class NetworkUpdateCoordinator(BaseDrainCoordinator):
    def __init__(
        self,
        reconcile_callback: Callable[[], None],
        economic_refresh_callback: Callable[[], None],
    ):
        super().__init__(debounce_seconds=0.2)
        self.reconcile_callback = reconcile_callback
        self.economic_refresh_callback = economic_refresh_callback

    def request(self, source: str | None = None) -> None:
        super().request(source)

    def _on_request(self, source: str | None) -> None:
        if source is None:
            return
        label = source.value if isinstance(source, NetworkUpdateSource) else source
        NETWORK_UPDATE_REQUESTS.labels(source=label).inc()
        NETWORK_UPDATE_PENDING.set(1)

    def _on_idle(self) -> None:
        NETWORK_UPDATE_PENDING.set(0)

    async def run_once(self) -> None:
        self.reconcile_callback()
        self.economic_refresh_callback()
        NETWORK_UPDATE_DRAINS.inc()
