from enum import Enum


class SessionLifecycleEvent(str, Enum):
    RETIRE_REQUESTED = "retire_requested"
    RETIRE_FAILED = "retire_failed"
    RETIRED = "retired"
    OPEN_REQUESTED = "open_requested"
    OPEN_RATE_LIMITED = "open_rate_limited"
    OPEN_FAILED = "open_failed"
    OPENED = "opened"
    OPEN_RACE_REUSED = "open_race_reused"
    MAINTENANCE_CLOSE_REQUESTED = "maintenance_close_requested"
    MAINTENANCE_CLOSE_FAILED = "maintenance_close_failed"
    MAINTENANCE_CLOSED = "maintenance_closed"


class NetworkUpdateSource(str, Enum):
    ACCOUNT_LINK_SUBSCRIPTION = "account_link_subscription"
    SAFE_BALANCE_REFRESH = "safe_balance_refresh"
    REDEEMED_REFRESH = "redeemed_refresh"
    PEER_DISCOVERY_REFRESH = "peer_discovery_refresh"
    CHANNEL_TOPOLOGY_REFRESH = "channel_topology_refresh"
    TICKET_PARAMETERS_CONFIGURATION = "ticket_parameters_configuration"
    TICKET_PARAMETERS_SUBSCRIPTION = "ticket_parameters_subscription"


class SessionOpenResult(str, Enum):
    REUSED_EXISTING = "reused_existing"
    RATE_LIMITED = "rate_limited"
    FAILED = "failed"
    OPENED = "opened"


class MessageSendFailureReason(str, Enum):
    TIMEOUT = "timeout"
    SESSION_CLOSED = "session_closed"
    SOCKET_ERROR = "socket_error"
    UNKNOWN = "unknown"


class MessageStatType(str, Enum):
    SENT = "sent"
    RECEIVED = "received"


class TicketStatType(str, Enum):
    PRICE = "price"
    MIN_TICKET_WINNING_PROBABILITY = "min_ticket_winning_probability"
