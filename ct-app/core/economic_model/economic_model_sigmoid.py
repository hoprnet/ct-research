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
        Calculates the APR for a given input value using the bucket's parameters.
        
        Args:
            x: The input value for which to compute the APR.
        
        Returns:
            The calculated APR, guaranteed to be non-negative.
        
        Raises:
            ValueError: If a math domain error, zero division, or overflow occurs during calculation.
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
    def __init__(self, offset: float, buckets: list[Bucket], max_apr: float, proportion: float):
        """
        Initializes an EconomicModelSigmoid instance with specified parameters.
        
        Args:
            offset: Value added to the APR calculation.
            buckets: List of Bucket instances used in APR computation.
            max_apr: Maximum allowable APR.
            proportion: Proportion factor for reward calculation.
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
        except ValueError as err:
            logger.exception("Value error in APR calculation", {"error": err})
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
