import logging
from math import log, pow, prod

from core.components.logs import configure_logging
from core.components.parameters import Parameters

from .budget import Budget

configure_logging()
logger = logging.getLogger(__name__)


class Bucket:
    def __init__(
        self,
        name: str,
        flatness: float,
        skewness: float,
        upperbound: float,
        offset: float = 0,
    ):
        self.name = name
        self.flatness = flatness
        self.skewness = skewness
        self.upperbound = upperbound
        self.offset = offset

    def apr(self, x: float):
        """
        Calculate the APR for the bucket.
        """
        try:
            apr = (
                log(pow(self.upperbound / x, self.skewness) - 1) * self.flatness
                + self.offset
            )
        except ValueError as e:
            raise ValueError(f"Math domain error: {x=}, {vars(self)}") from e
        except ZeroDivisionError as e:
            raise ValueError("Zero division error") from e
        except OverflowError as e:
            raise ValueError("Overflow error") from e

        return max(apr, 0)

    @classmethod
    def fromParameters(cls, name: str, parameters: Parameters):
        return cls(
            name,
            parameters.flatness,
            parameters.skewness,
            parameters.upperbound,
            parameters.offset,
        )


class EconomicModelSigmoid:
    def __init__(
        self, offset: float, buckets: list[Bucket], max_apr: float, proportion: float
    ):
        """
        Initialisation of the class.
        """
        self.offset = offset
        self.buckets = buckets
        self.max_apr = max_apr
        self.proportion = proportion
        self.budget: Budget = Budget()

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
                    prod(b.apr(x) for b, x in zip(self.buckets, xs)),
                    1 / len(self.buckets),
                )
                + self.offset
            )
        except ValueError as e:
            logger.error(f"Value error in APR calculation: {e}")
            apr = 0

        if self.max_apr is not None:
            apr = min(apr, self.max_apr)

        return apr

    def yearly_message_count(self, stake: float, xs: list[float]):
        """
        Calculate the yearly message count a peer should receive based on the stake.
        """
        apr = self.apr(xs)

        rewards = apr * stake / 100.0

        return rewards / self.budget.ticket_price * self.proportion

    @classmethod
    def fromParameters(cls, parameters: Parameters):
        bucket_names = vars(parameters.buckets)

        return cls(
            parameters.offset,
            [
                Bucket.fromParameters(name, getattr(parameters.buckets, name))
                for name in bucket_names
            ],
            parameters.maxAPR,
            parameters.proportion,
        )

    def __repr__(self):
        return f"EconomicModelSigmoid({self.offset}, {self.buckets}, {self.budget})"

    @property
    def print_prefix(self) -> str:
        return "EconomicModelSigmoid"
