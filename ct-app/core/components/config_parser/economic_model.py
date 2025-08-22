import logging
from dataclasses import dataclass
from decimal import Decimal
from math import log, prod
from typing import Optional

from core.api.response_objects import TicketPrice

from ..balance import Balance
from ..logs import configure_logging
from .base_classes import ExplicitParams

configure_logging()
logger = logging.getLogger(__name__)


@dataclass(init=False)
class LegacyCoefficientsParams(ExplicitParams):
    a: Decimal
    b: Decimal
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
    apr: Decimal
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
        redeemed_rewards: Optional[Balance] = None,
    ) -> float:
        """
        Calculate the yearly message count a peer should receive based on the stake.
        """

        self.coefficients.upperbound += redeemed_rewards or Balance.zero(("wxHOPR"))
        rewards = self.apr * self.transformed_stake(stake) / 100
        self.coefficients.upperbound -= redeemed_rewards or Balance.zero(("wxHOPR"))

        return float(rewards / ticket_price.value * self.proportion)


@dataclass(init=False)
class BucketParams(ExplicitParams):
    flatness: Decimal
    skewness: Decimal
    upperbound: Decimal
    offset: Decimal

    def apr(self, x: Decimal) -> Decimal:
        """
        Calculate the APR for the bucket.
        """
        try:
            apr = (
                Decimal(log(pow(self.upperbound / x, self.skewness) - 1)) * self.flatness
                + self.offset
            )
        except ValueError as err:
            raise ValueError(f"Math domain error: {x=}, {vars(self)}") from err
        except ZeroDivisionError as err:
            raise ValueError("Zero division error") from err
        except OverflowError as err:
            raise ValueError("Overflow error") from err

        return max(apr, Decimal(0))


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
    max_apr: Decimal
    offset: Decimal
    buckets: BucketsParams
    network_capacity: int
    total_token_supply: Balance

    def apr(
        self,
        xs: list[Decimal],
    ) -> Decimal:
        """
        Calculate the APR for the economic model.
        """
        try:
            apr: Decimal = (
                pow(
                    prod(b.apr(x) for b, x in zip(self.buckets.values, xs)),
                    Decimal(1 / self.buckets.count),
                )
                + self.offset
            )
        except ValueError as err:
            logger.exception("Value error in APR calculation", {"error": err})
            apr: Decimal = Decimal(0)

        if self.max_apr is not None:
            apr: Decimal = min(apr, self.max_apr)

        return apr

    def yearly_message_count(
        self, stake: Balance, ticket_price: TicketPrice, xs: list[Decimal]
    ) -> float:
        """
        Calculate the yearly message count a peer should receive based on the stake.
        """
        apr: Decimal = self.apr(xs)

        rewards: Decimal = apr * stake / Decimal(100.0)

        return float(rewards / ticket_price.value * self.proportion)


@dataclass(init=False)
class EconomicModelParams(ExplicitParams):
    min_safe_allowance: Balance
    nft_threshold: Balance
    legacy: LegacyParams
    sigmoid: SigmoidParams

    @property
    def models(self):
        return {v.__class__: k for k, v in vars(self).items() if isinstance(v, ExplicitParams)}
