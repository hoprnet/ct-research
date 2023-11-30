from enum import Enum


class TaskStatus(Enum):
    """
    Enum to represent the status of a task. This status is also used when creating a
    task in the outgoing queue.
    """

    DEFAULT = "DEFAULT"
    SUCCESS = "SUCCESS"
    RETRIED = "RETRIED"
    SPLIT = "SPLIT"
    TIMEOUT = "TIMEOUT"
    FAILED = "FAILED"
