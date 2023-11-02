from enum import Enum


class ChannelStatus(Enum):
    Open = "Open"
    PendingToClose = "PendingToClose"
    Closed = "Closed"

    @classmethod
    def is_pending(cls, value: str):
        return value == cls.PendingToClose.value

    @classmethod
    def is_open(cls, value: str):
        return value == cls.Open.value
