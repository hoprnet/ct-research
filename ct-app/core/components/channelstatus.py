from enum import Enum


class ChannelStatus(Enum):
    Open = "Open"
    PendingToClose = "PendingToClose"
    Closed = "Closed"

    @property
    def isPending(self):
        return self == self.PendingToClose

    @property
    def isOpen(self):
        return self == self.Open

    @property
    def isClosed(self):
        return self == self.Closed

    @classmethod
    def fromString(cls, value: str):
        for status in cls:
            if status.value == value:
                return status

        return None
