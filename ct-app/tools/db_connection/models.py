from datetime import datetime
import random

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class NodePeerConnection(Base):
    __tablename__ = "metricTable"
    id: Mapped[int] = mapped_column(primary_key=True)
    peer_id: Mapped[str]
    node: Mapped[str]
    latency: Mapped[int]
    order: Mapped[int]

    timestamp: Mapped[datetime] = mapped_column(DateTime)

    def __repr__(self) -> str:
        return (
            f"Metric(id={self.id!r}, "
            + f"peer_id={self.peer_id!r}, "
            + f"node={self.node!r}, "
            + f"latency={self.latency!r}, "
            + f"order={self.order!r}, "
            + f"timestamp={self.timestamp})"
        )

    @classmethod
    def random(cls, count: int):
        timestamp = datetime.now()
        peer_id = f"peer_id_{random.randint(0, 99):02}"

        instances = [
            cls(
                peer_id=peer_id,
                node=f"random_node_{random.randint(0, 99):02}",
                latency=random.randint(1, 100),
                order=order,
                timestamp=timestamp,
            )
            for order in range(count)
        ]

        return instances


class Reward(Base):
    __tablename__ = "rewardTable"
    id: Mapped[int] = mapped_column(primary_key=True)
    peer_id: Mapped[str]
    node_address: Mapped[str]
    expected_count: Mapped[int]
    effective_count: Mapped[int]
    status: Mapped[str]
    timestamp: Mapped[datetime] = mapped_column(DateTime)

    def __repr__(self) -> str:
        return (
            f"Reward(id={self.id!r}, peer_id={self.peer_id!r}, "
            + f"node_address={self.node_address!r}, "
            + f"expected_count={self.expected_count!r}, "
            + f"effective_count={self.effective_count!r}, "
            + f"status={self.status!r}, "
            + f"timestamp={self.timestamp})"
        )

    @classmethod
    def random(cls):
        expected_count = random.randint(10, 20)
        return cls(
            peer_id=f"peer_id_{random.randint(0, 99):02}",
            node_address=f"node_address_{random.randint(0, 99):02}",
            expected_count=expected_count,
            effective_count=random.randint(0, expected_count),
            status="TEST",
            timestamp=datetime.now(),
        )
