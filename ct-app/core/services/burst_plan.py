"""
Round and burst arithmetic of the burst incentive model (see PROTOCOL_v2.md, §3 to §5).

Everything here is derived from the configuration and the network values; nothing is stored.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from math import ceil
from typing import Optional

from ..config_parser.incentive import IncentiveParams
from ..types.balance import Balance

SECONDS_IN_A_MONTH = 30 * 24 * 60 * 60
BITS_PER_MBIT = 1_000_000
BITS_PER_BYTE = 8

# Every packet a CT node sends crosses the relayer twice, out to the destination and back as its
# echo, and the relayer gets a ticket each time. `burst_rate` is the traffic relayed (and paid
# for), so a CT node sends at `burst_rate / RELAYER_CROSSINGS_PER_PACKET`.
RELAYER_CROSSINGS_PER_PACKET = 2


def packet_rate(burst_rate: float, mtu: int) -> float:
    """
    Packets per second the relayer forwards during a burst, both directions together. A whole
    packet is `mtu` bytes, SURB included.
    """
    return burst_rate * BITS_PER_MBIT / (BITS_PER_BYTE * mtu)


def send_rate(burst_rate: float, mtu: int) -> float:
    """Packets per second a CT node sends during a burst."""
    return packet_rate(burst_rate, mtu) / RELAYER_CROSSINGS_PER_PACKET


def packets_per_burst(burst_rate: float, burst_duration: float, mtu: int) -> int:
    """Packets a CT node sends in one burst."""
    return round(send_rate(burst_rate, mtu) * burst_duration)


@dataclass(frozen=True)
class RoundPlan:
    relayer_count: int
    ct_node_count: int
    round_duration: float
    step: float
    concurrency: float
    burst_duration: float
    burst_rate: float
    capped: bool

    @classmethod
    def build(cls, params: IncentiveParams, relayer_count: int) -> "RoundPlan":
        interval = params.target_relayer_interval.value
        burst_duration = params.burst_duration.value
        ct_node_count = params.ct_node_count
        cap = params.max_concurrent_bursts_per_ct

        if ct_node_count < 1 or interval <= 0 or burst_duration <= 0 or params.burst_rate <= 0:
            raise ValueError(
                "Invalid incentive parameters: ct_node_count, target_relayer_interval, "
                "burst_duration and burst_rate must be positive"
            )
        if relayer_count < 1:
            raise ValueError("A round needs at least one relayer")

        round_duration = ct_node_count * interval
        capped = False
        if cap > 0 and ceil(relayer_count * burst_duration / round_duration) > cap:
            round_duration = max(round_duration, relayer_count * burst_duration / cap)
            capped = True

        return cls(
            relayer_count=relayer_count,
            ct_node_count=ct_node_count,
            round_duration=round_duration,
            step=round_duration / relayer_count,
            concurrency=relayer_count * burst_duration / round_duration,
            burst_duration=burst_duration,
            burst_rate=params.burst_rate,
            capped=capped,
        )

    @property
    def peak_concurrency(self) -> int:
        return max(1, ceil(self.concurrency))

    @property
    def relayer_interval(self) -> float:
        return self.round_duration / self.ct_node_count

    @property
    def avg_outbound_mbps(self) -> float:
        return self.burst_rate / RELAYER_CROSSINGS_PER_PACKET * self.concurrency

    @property
    def peak_outbound_mbps(self) -> float:
        return self.burst_rate / RELAYER_CROSSINGS_PER_PACKET * self.peak_concurrency

    @property
    def bursts_per_relayer_per_month(self) -> float:
        return SECONDS_IN_A_MONTH / self.relayer_interval

    def packets_per_burst(self, mtu: int) -> int:
        return packets_per_burst(self.burst_rate, self.burst_duration, mtu)

    def packets_per_relayer_per_month(self, mtu: int) -> float:
        """Packets the relayer forwards (and gets a ticket for), both directions together."""
        packets = packet_rate(self.burst_rate, mtu) * self.burst_duration
        return self.bursts_per_relayer_per_month * packets

    def max_reward_per_relayer_month(self, mtu: int, ticket_price: Balance) -> Balance:
        return ticket_price * Decimal(str(self.packets_per_relayer_per_month(mtu)))

    def max_monthly_cost(self, mtu: int, ticket_price: Balance) -> Balance:
        return self.max_reward_per_relayer_month(mtu, ticket_price) * self.relayer_count

    def summary(
        self, mtu: Optional[int] = None, ticket_price: Optional[Balance] = None
    ) -> dict[str, object]:
        summary: dict[str, object] = {
            "relayers": self.relayer_count,
            "round_duration_s": round(self.round_duration, 3),
            "step_s": round(self.step, 3),
            "concurrency": round(self.concurrency, 3),
            "peak_concurrency": self.peak_concurrency,
            "capped": self.capped,
            "relayer_interval_s": round(self.relayer_interval, 3),
            "avg_outbound_mbps": round(self.avg_outbound_mbps, 3),
            "peak_outbound_mbps": round(self.peak_outbound_mbps, 3),
        }
        if mtu:
            summary["mtu"] = mtu
            summary["packets_per_burst"] = self.packets_per_burst(mtu)
            if ticket_price is not None:
                summary["max_reward_per_relayer_month"] = round(
                    self.max_reward_per_relayer_month(mtu, ticket_price), 4
                ).as_str
                summary["projected_max_monthly_cost"] = round(
                    self.max_monthly_cost(mtu, ticket_price), 4
                ).as_str
        return summary


class RelayedCostTracker:
    """
    Month-to-date (UTC calendar month) count of burst packets and their cost. An echoed packet
    crossed the relayer twice, so it costs two tickets.
    """

    def __init__(self) -> None:
        self.month: Optional[tuple[int, int]] = None
        self.packets_sent = 0
        self.packets_echoed = 0
        self.cost: Optional[Balance] = None

    def _roll(self, now: datetime) -> None:
        month = (now.year, now.month)
        if month != self.month:
            self.month = month
            self.packets_sent = 0
            self.packets_echoed = 0
            self.cost = None

    def add(
        self,
        sent: int,
        echoed: int,
        ticket_price: Optional[Balance],
        now: Optional[datetime] = None,
    ) -> Optional[Balance]:
        """Record a finished burst and return its cost (None without a known ticket price)."""
        self._roll(now or datetime.now(timezone.utc))
        self.packets_sent += sent
        self.packets_echoed += echoed
        if ticket_price is None:
            return None

        burst_cost = ticket_price * (echoed * RELAYER_CROSSINGS_PER_PACKET)
        self.cost = burst_cost if self.cost is None else self.cost + burst_cost
        return burst_cost

    def summary(self, now: Optional[datetime] = None) -> dict[str, object]:
        self._roll(now or datetime.now(timezone.utc))
        return {
            "month_to_date_packets_sent": self.packets_sent,
            "month_to_date_packets_echoed": self.packets_echoed,
            "month_to_date_cost": self.cost.as_str if self.cost is not None else None,
        }
