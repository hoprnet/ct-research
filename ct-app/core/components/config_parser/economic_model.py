import logging
from dataclasses import dataclass
from decimal import Decimal
from math import log, prod

from core.api.response_objects import TicketPrice
from core.components.balance import Balance
from core.components.logs import configure_logging

from .base_classes import ExplicitParams

configure_logging()
logger = logging.getLogger(__name__)


@dataclass(init=False)
class LegacyCoefficientsParams(ExplicitParams):
    a: float
    b: float
    lowerbound: Balance
    upperbound: Balance


@dataclass(init=False)
class LegacyEquationParams(ExplicitParams):
    formula: str
    condition: str


@dataclass(init=False)
class LegacyEquationsParams(ExplicitParams):
    fx: LegacyEquationParams
    gx: LegacyEquationParams


@dataclass(init=False)
class LegacyParams(ExplicitParams):
    proportion: Decimal
    apr: float
    coefficients: LegacyCoefficientsParams
    equations: LegacyEquationsParams

    def transformed_stake(self, stake: Balance) -> Balance:
        # convert parameters attribute to dictionary
        kwargs = dict(vars(self.coefficients).items())
        kwargs.update({"x": stake})

        for func in vars(self.equations).values():
            if eval(func.condition, kwargs):
                break
        else:
            return Balance.zero(("wxHOPR"))

        return eval(func.formula, kwargs)

    def yearly_message_count(
        self,
        stake: Balance,
        ticket_price: TicketPrice,
        redeemed_rewards: Balance = Balance.zero("wxHOPR"),
    ) -> float:
        """
        Calculate the yearly message count a peer should receive based on the stake.
        """
        self.coefficients.upperbound += redeemed_rewards
        rewards = self.apr * self.transformed_stake(stake) / 100
        self.coefficients.upperbound -= redeemed_rewards

        return rewards / ticket_price.value * self.proportion


@dataclass(init=False)
class BucketParams(ExplicitParams):
    flatness: float
    skewness: float
    upperbound: float
    offset: float

    def apr(self, x: float) -> float:
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

        return max(apr, 0.0)


@dataclass(init=False)
class BucketsParams(ExplicitParams):
    economic_security: BucketParams
    network_capacity: BucketParams

    order = ["network_capacity", "economic_security"]

    @property
    def count(self):
        return len(self.values)

    @property
    def values(self):
        return [vars(self)[k] for k in self.order if k in vars(self) and vars(self)[k]]


@dataclass(init=False)
class SigmoidParams(ExplicitParams):
    proportion: Decimal
    max_apr: float
    offset: float
    buckets: BucketsParams
    network_capacity: int
    total_token_supply: Balance

    def apr(
        self,
        xs: list[float],
    ) -> float:
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

    def yearly_message_count(self, stake: Balance, ticket_price: TicketPrice, xs: list[float]):
        """
        Calculate the yearly message count a peer should receive based on the stake.
        """
        apr = self.apr(xs)

        rewards = apr * stake / 100.0

        return rewards / ticket_price.value * self.proportion


@dataclass(init=False)
class EconomicModelParams(ExplicitParams):
    min_safe_allowance: Balance
    nft_threshold: Balance
    legacy: LegacyParams
    sigmoid: SigmoidParams

    @property
    def models(self):
        return {v: k for k, v in vars(self).items() if isinstance(v, ExplicitParams)}
