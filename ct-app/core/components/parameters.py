import logging

from core.components.logs import configure_logging

configure_logging()
logger = logging.getLogger(__name__)


class ExplicitParams:
    keys: dict[str, type] = {}

    def __init__(self, data: dict):
        self.parse(data)

    def parse(self, data: dict):
        for name, type in self.keys.items():
            if value := data.get(name):
                value = type(value)
            setattr(self, name, value)

    @property
    def as_dict(self):
        return {k: v.as_dict if isinstance(v, ExplicitParams) else v for k, v in self.__dict__.items()}

class FlagParam(ExplicitParams):
    keys = {
        "value": int
    }

class FlagCoreParams(ExplicitParams):
    keys = {
        "apply_economic_model": FlagParam,
        "ticket_parameters": FlagParam,
        "connected_peers": FlagParam,
        "topology": FlagParam,
        "rotate_subgraphs": FlagParam,
        "peers_rewards": FlagParam,
        "registered_nodes": FlagParam,
        "allocations": FlagParam,
        "eoa_balances": FlagParam,
        "nft_holders": FlagParam,
        "safe_fundings": FlagParam
    }


class FlagNodeParams(ExplicitParams):
    keys = {
        "healthcheck": FlagParam,
        "retrieve_peers": FlagParam, 
        "retrieve_channels": FlagParam,
        "retrieve_balances": FlagParam, 
        "open_channels": FlagParam,
        "fund_channels": FlagParam,
        "close_old_channels": FlagParam,
        "close_pending_channels": FlagParam,
        "close_incoming_channels": FlagParam,
        "get_total_channel_funds": FlagParam,
        "observe_message_queue": FlagParam,
        "observe_relayed_messages": FlagParam,
    }


class FlagPeerParams(ExplicitParams):
    keys = {
        "message_relay_request": FlagParam
    }


class FlagParams(ExplicitParams):
    keys = {
        "core": FlagCoreParams,
        "node": FlagNodeParams,
        "peer": FlagPeerParams
    }


class LegacyCoefficientsParams(ExplicitParams):
    keys = {
        "a": float,
        "b": float,
        "c": float,
        "l": float,
    }


class LegacyEquationParams(ExplicitParams):
    keys = {
        "formula": str,
        "condition": str,
    }


class LegacyEquationsParams(ExplicitParams):
    keys = {
        "fx": LegacyEquationParams,
        "gx": LegacyEquationParams,
    }


class LegacyParams(ExplicitParams):
    keys = {
        "proportion": float,
        "apr": float,
        "coefficients": LegacyCoefficientsParams,
        "equations": LegacyEquationsParams
    }


class BucketParams(ExplicitParams):
    keys = {
        "flatness": float,
        "skewness": float,
        "upperbound": float,
        "offset": float
    }


class BucketsParams(ExplicitParams):
    keys = {
        "economic_security": BucketParams,
        "network_capacity": BucketParams
    }


class SigmoidParams(ExplicitParams):
    keys = {
        "proportion": float,
        "max_apr": float,
        "network_capacity": int,
        "total_token_supply": int,
        "offset": int,
        "buckets": BucketsParams
    }


class EconomicModelParams(ExplicitParams):
    keys = {
        "min_safe_allowance": float,
        "nft_threshold": float,
        "legacy": LegacyParams,
        "sigmoid": SigmoidParams
    }


class PeerParams(ExplicitParams):
    keys = {
        "min_version": str,
        "sleep_mean_time": int,
        "sleep_std_time": int
    }


class ChannelParams(ExplicitParams):
    keys = {
        "min_balance": float,
        "funding_amount": float,
        "max_age_seconds": int
    }


class FundingsParams(ExplicitParams):
    keys = {
        "constant": float
    }


class SubgraphEndpointInputsParams(ExplicitParams):
    keys = {
        "schedule_in": list[str]
    }


class SubgraphEndpointParams(ExplicitParams):
    keys = {
        "query_id": str,
        "slug": str,
        "inputs": SubgraphEndpointInputsParams
    }


class SubgraphParams(ExplicitParams):
    keys = {
        "mainnet_allocations": SubgraphEndpointParams,
        "gnosis_allocations": SubgraphEndpointParams,
        "hopr_on_mainnet": SubgraphEndpointParams,
        "hopr_on_gnosis": SubgraphEndpointParams,
        "safes_balance": SubgraphEndpointParams,
        "fundings": SubgraphEndpointParams,
        "rewards": SubgraphEndpointParams,
        "staking": SubgraphEndpointParams
    }


class Parameters(ExplicitParams):
    keys = {
        "flags": FlagParams,
        "economic_model": EconomicModelParams,
        "peer": PeerParams,
        "channel": ChannelParams,
        "fundings": FundingsParams,
        "subgraph": SubgraphParams
    }
