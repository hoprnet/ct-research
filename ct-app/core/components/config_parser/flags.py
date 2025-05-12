from .base_classes import ExplicitParams, Flag


class FlagCoreParams(ExplicitParams):
    keys = {
        "apply_economic_model": Flag,
        "ticket_parameters": Flag,
        "connected_peers": Flag,
        "topology": Flag,
        "rotate_subgraphs": Flag,
        "open_sessions": Flag,
        "peers_rewards": Flag,
        "registered_nodes": Flag,
        "allocations": Flag,
        "eoa_balances": Flag,
        "nft_holders": Flag,
        "safe_fundings": Flag,
    }


class FlagNodeParams(ExplicitParams):
    keys = {
        "healthcheck": Flag,
        "retrieve_peers": Flag,
        "retrieve_channels": Flag,
        "retrieve_balances": Flag,
        "open_channels": Flag,
        "fund_channels": Flag,
        "close_old_channels": Flag,
        "close_pending_channels": Flag,
        "close_incoming_channels": Flag,
        "get_total_channel_funds": Flag,
        "observe_message_queue": Flag,
        "close_sessions": Flag,
    }


class FlagPeerParams(ExplicitParams):
    keys = {"message_relay_request": Flag}


class FlagParams(ExplicitParams):
    keys = {"core": FlagCoreParams, "node": FlagNodeParams, "peer": FlagPeerParams}
