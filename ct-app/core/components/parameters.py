import logging
from math import log, prod

from core.api.response_objects import TicketPrice
from core.components.logs import configure_logging

configure_logging()
logger = logging.getLogger(__name__)


class ExplicitParams:
    keys: dict[str, type] = {}

    def __init__(self, data: dict | None = None):
        if data is None:
            data = {}
        self.parse(data)

    def parse(self, data: dict):
        for name, type in self.keys.items():
            if value := data.get(name):
                value = type(value)
                if type is Flag:
                    value = value.value
            setattr(self, name, value)

    @property
    def as_dict(self):
        return {
            k: v.as_dict if isinstance(v, ExplicitParams) else v
            for k, v in self.__dict__.items()
        }

    def __repr__(self):
        return f"{self.__class__.__name__}({self.as_dict})"


class Flag:
    def __init__(self, value: int):
        self.value = value


class FlagCoreParams(ExplicitParams):
    keys = {
        "apply_economic_model": Flag,
        "ticket_parameters": Flag,
        "connected_peers": Flag,
        "topology": Flag,
        "rotate_subgraphs": Flag,
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
        "observe_relayed_messages": Flag,
    }


class FlagPeerParams(ExplicitParams):
    keys = {"message_relay_request": Flag}


class FlagParams(ExplicitParams):
    keys = {"core": FlagCoreParams, "node": FlagNodeParams, "peer": FlagPeerParams}


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
        "equations": LegacyEquationsParams,
    }

    def transformed_stake(self, stake: float):
        # convert parameters attribute to dictionary
        kwargs = vars(self.coefficients)
        kwargs.update({"x": stake})

        for func in vars(self.equations).values():
            if eval(func.condition, kwargs):
                break
        else:
            return 0

        return eval(func.formula, kwargs)

    def yearly_message_count(
        self, stake: float, ticket_price: TicketPrice, redeemed_rewards: float = 0
    ):
        """
        Calculate the yearly message count a peer should receive based on the stake.
        """
        self.coefficients.c += redeemed_rewards
        rewards = self.apr * self.transformed_stake(stake) / 100
        self.coefficients.c -= redeemed_rewards

        return rewards / ticket_price.value * self.proportion


class BucketParams(ExplicitParams):
    keys = {"flatness": float, "skewness": float, "upperbound": float, "offset": float}

    def apr(self, x: float):
        """
        Calculate the APR for the bucket.
        """
        try:
            apr = (
                log(pow(self.upperbound / x, self.skewness) - 1) * self.flatness
                + self.offset
            )
        except ValueError as err:
            raise ValueError(f"Math domain error: {x=}, {vars(self)}") from err
        except ZeroDivisionError as err:
            raise ValueError("Zero division error") from err
        except OverflowError as err:
            raise ValueError("Overflow error") from err

        return max(apr, 0)


class BucketsParams(ExplicitParams):
    keys = {"economic_security": BucketParams, "network_capacity": BucketParams}

    order = ["network_capacity", "economic_security"]

    @property
    def count(self):
        return len(self.values)

    @property
    def values(self):
        # return the values of the dictionary, by `order`
        return [vars(self)[k] for k in self.order if vars(self)[k]]


class SigmoidParams(ExplicitParams):
    keys = {
        "proportion": float,
        "max_apr": float,
        "offset": int,
        "buckets": BucketsParams,
        "network_capacity": int,
        "total_token_supply": int,
    }

    def apr(
        self,
        xs: list[float],
    ):
        """
        Calculate the APR for the economic model.
        """
        try:
            apr = (
                pow(
                    prod(b.apr(x) for b, x in zip(self.buckets.values, xs)),
                    1 / self.buckets.count,
                )
                + self.offset
            )
        except ValueError as err:
            logger.exception("Value error in APR calculation", {"error": err})
            apr = 0

        if self.max_apr is not None:
            apr = min(apr, self.max_apr)

        return apr

    def yearly_message_count(
        self, stake: float, ticket_price: TicketPrice, xs: list[float]
    ):
        """
        Calculate the yearly message count a peer should receive based on the stake.
        """
        apr = self.apr(xs)

        rewards = apr * stake / 100.0

        return rewards / ticket_price.value * self.proportion


class EconomicModelParams(ExplicitParams):
    keys = {
        "min_safe_allowance": float,
        "nft_threshold": float,
        "legacy": LegacyParams,
        "sigmoid": SigmoidParams,
    }

    @property
    def models(self):
        return {v: k for k, v in vars(self).items() if isinstance(v, ExplicitParams)}


class PeerParams(ExplicitParams):
    keys = {
        "min_version": str,
        "sleep_mean_time": int,
        "sleep_std_time": int,
        "message_multiplier": int,
    }


class ChannelParams(ExplicitParams):
    keys = {"min_balance": float, "funding_amount": float, "max_age_seconds": int}


class FundingsParams(ExplicitParams):
    keys = {"constant": float}


class SubgraphEndpointParams(ExplicitParams):
    keys = {"query_id": str, "slug": str, "inputs": dict}


class SubgraphParams(ExplicitParams):
    keys = {
        "type": str,
        "user_id": int,
        "api_key": str,
        "mainnet_allocations": SubgraphEndpointParams,
        "gnosis_allocations": SubgraphEndpointParams,
        "hopr_on_mainnet": SubgraphEndpointParams,
        "hopr_on_gnosis": SubgraphEndpointParams,
        "safes_balance": SubgraphEndpointParams,
        "fundings": SubgraphEndpointParams,
        "rewards": SubgraphEndpointParams,
        "staking": SubgraphEndpointParams,
    }


class Parameters(ExplicitParams):
    keys = {
        "flags": FlagParams,
        "economic_model": EconomicModelParams,
        "peer": PeerParams,
        "channel": ChannelParams,
        "fundings": FundingsParams,
        "subgraph": SubgraphParams,
    }
