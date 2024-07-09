from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Reward(Base):
    __tablename__ = "rewards"
    id: Mapped[int] = mapped_column(primary_key=True)
    peer_id: Mapped[str]
    count: Mapped[int]
    value: Mapped[float]
    timestamp: Mapped[datetime] = mapped_column(DateTime)

    def __repr__(self) -> str:
        return (
            f"Reward(id={self.id!r}, peer_id={self.peer_id!r}, "
            + f"count={self.count!r}, value={self.value!r}, "
            + f"timestamp={self.timestamp})"
        )
