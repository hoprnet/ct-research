from datetime import datetime

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
    priority: Mapped[int]

    timestamp: Mapped[datetime] = mapped_column(DateTime)

    def __repr__(self) -> str:
        return (
            f"Metric(id={self.id!r}, "
            + f"peer_id={self.peer_id!r}, "
            + f"node={self.node!r}, "
            + f"latency={self.latency!r}, "
            + f"priority={self.priority!r}, "
            + f"timestamp={self.timestamp})"
        )


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


class Peer(Base):
    __tablename__ = "peerTable"
    id: Mapped[int] = mapped_column(primary_key=True)
    peer_id: Mapped[str]

    def __repr__(self) -> str:
        return f"Peer(id={self.id!r}, peer_id={self.peer_id!r})"
