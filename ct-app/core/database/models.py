from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SentMessages(Base):
    __tablename__ = "sent_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    relayer: Mapped[str]
    count: Mapped[int]
    timestamp: Mapped[datetime] = mapped_column(DateTime)

    def __repr__(self) -> str:
        return (
            f"Reward(id={self.id!r}, relayer={self.relayer!r}, "
            + f"count={self.count!r}, "
            + f"timestamp={self.timestamp})"
        )


class RelayedMessages(Base):
    __tablename__ = "relayed_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    relayer: Mapped[str]
    sender: Mapped[str]
    count: Mapped[int]
    timestamp: Mapped[datetime] = mapped_column(DateTime)

    def __repr__(self) -> str:
        return (
            f"Reward(id={self.id!r}, relayer={self.relayer!r}, "
            + f"sender={self.sender!r}, "
            + f"count={self.count!r}, "
            + f"timestamp={self.timestamp})"
        )
