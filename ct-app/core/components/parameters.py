import logging

from core.components.logs import configure_logging

configure_logging()
logger = logging.getLogger(__name__)


class Param:
    def __init__(self, name: str, type: type = str, default=None):
        self.name = name
        self.type = type
        self.default = default


class ExplicitParams:
    keys: dict[str, Param] = {}

    def __init__(self, data: dict):
        self.parse(data)

    def parse(self, data: dict):
        for in_file, param in self.keys.items():
            if value := data.get(in_file):
                value = param.type(value)
            setattr(self, param.name, value)

    @property
    def as_dict(self):
        return {k: v.as_dict if isinstance(v, ExplicitParams) else v for k, v in self.__dict__.items()}


class FlagParams(ExplicitParams):
    pass


class LegacyCoefficientsParams(ExplicitParams):
    keys = {
        "a": Param("a", float),
        "b": Param("b", float),
        "c": Param("c", float),
        "l": Param("l", float)
    }


class LegacyEquationParams(ExplicitParams):
    keys = {
        "formula": Param("formula"),
        "condition": Param("condition"),
    }


class LegacyEquationsParams(ExplicitParams):
    keys = {
        "fx": Param("fx", LegacyEquationParams),
        "gx": Param("gx", LegacyEquationParams),
    }


class LegacyParams(ExplicitParams):
    keys = {
        "proportion": Param("proportion", float),
        "apr": Param("apr", float),
        "coefficients": Param("coefficients", LegacyCoefficientsParams),
        "equations": Param("equations", LegacyEquationsParams)
    }


class BucketParams(ExplicitParams):
    keys = {
        "flatness": Param("flatness", float),
        "skewness": Param("skewness", float),
        "upperbound": Param("upperbound", float),
        "offset": Param("offset", float)
    }


class BucketsParams(ExplicitParams):
    keys = {
        "economicSecurity": Param("economic_security", BucketParams),
        "networkCapacity": Param("network_capacity", BucketParams)
    }


class SigmoidParams(ExplicitParams):
    keys = {
        "proportion": Param("proportion", float),
        "maxAPR": Param("max_apr", float),
        "networkCapacity": Param("network_capacity", int),
        "totalTokenSupply": Param("total_token_supply", int),
        "offset": Param("offset", int),
        "buckets": Param("buckets", BucketsParams)
    }


class EconomicModelParams(ExplicitParams):
    keys = {
        "minSafeAllowance": Param("min_safe_allowance", float),
        "NFTThreshold": Param("nft_threshold", float),
        "legacy": Param("legacy", LegacyParams),
        "sigmoid": Param("sigmoid", SigmoidParams)
    }


class PeerParams(ExplicitParams):
    keys = {
        "minVersion": Param("min_version"),
        "sleepMeanTime": Param("sleep_mean_time", int),
        "sleepStdTime": Param("sleep_std_time", int),
    }


class ChannelParams(ExplicitParams):
    keys = {
        "minBalance": Param("min_balance", float),
        "fundingAmount": Param("funding_amount", float),
        "maxAgeSeconds": Param("max_age_seconds", int)
    }


class FundingsParams(ExplicitParams):
    keys = {
        "constant": Param("constant", float)
    }


class SubgraphEndpointInputsParams(ExplicitParams):
    keys = {
        "schedule_in": Param("schedule_in", list[str])
    }


class SubgraphEndpointParams(ExplicitParams):
    keys = {
        "queryID": Param("query_id"),
        "slug": Param("slug"),
        "inputs": Param("inputs", SubgraphEndpointInputsParams)
    }


class SubgraphParams(ExplicitParams):
    keys = {
        "mainnetAllocations": Param("mainnet_allocations", SubgraphEndpointParams),
        "gnosisAllocations": Param("gnosis_allocations", SubgraphEndpointParams),
        "hoprOnMainnet": Param("hopr_on_mainnet", SubgraphEndpointParams),
        "hoprOnGnosis": Param("hopr_on_gnosis", SubgraphEndpointParams),
        "fundings": Param("fundings", SubgraphEndpointParams),
        "rewards": Param("rewards", SubgraphEndpointParams),
        "safesBalance": Param("safes_balance", SubgraphEndpointParams),
        "staking": Param("staking", SubgraphEndpointParams),
    }


class Parameters(ExplicitParams):
    keys = {
        "flags": Param("flags", FlagParams),
        "economicModel": Param("economic_model", EconomicModelParams),
        "peer": Param("peer", PeerParams),
        "channel": Param("channel", ChannelParams),
        "fundings": Param("fundings", FundingsParams),
        "subgraph": Param("subgraph", SubgraphParams)
    }
