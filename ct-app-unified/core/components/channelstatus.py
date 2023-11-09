from enum import Enum


class ChannelStatus(Enum):
    Open = "Open"
    PendingToClose = "PendingToClose"
    Closed = "Closed"

    @classmethod
    def isPending(cls, value: str):
        return value == cls.PendingToClose.value

    @classmethod
    def isOpen(cls, value: str):
        return value == cls.Open.value
