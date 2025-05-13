import logging
from math import log, prod

from core.api.response_objects import TicketPrice
from core.components.logs import configure_logging

from .base_classes import ExplicitParams

configure_logging()
logger = logging.getLogger(__name__)


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
            apr = log(pow(self.upperbound / x, self.skewness) - 1) * self.flatness + self.offset
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

    def yearly_message_count(self, stake: float, ticket_price: TicketPrice, xs: list[float]):
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
