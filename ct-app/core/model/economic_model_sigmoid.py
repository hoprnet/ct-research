from math import log, pow, prod

from core.components.baseclass import Base
from core.components.parameters import Parameters

from .budget import Budget


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


class EconomicModelSigmoid(Base):
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
        self.budget: Budget = None

    def apr(self, xs: list[float]):
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
            self.error(f"Value error in APR calculation: {e}")
            apr = 0

        if self.max_apr is not None:
            apr = min(apr, self.max_apr)

        return apr

    def message_count_for_reward(self, stake: float, xs: list[float]):
        """
        Calculate the message count for the reward.
        """
        apr = self.apr(xs)

        yearly_rewards = apr * stake / 100.0
        rewards = yearly_rewards / (365 * 86400 / self.budget.intervals)

        under = self.budget.ticket_price * self.budget.winning_probability

        return round(self.proportion * rewards / under) if under != 0 else 0

    @classmethod
    def fromParameters(cls, parameters: Parameters):
        return cls(
            parameters.offset,
            [
                Bucket.fromParameters(name, getattr(parameters.buckets, name))
                for name in vars(parameters.buckets)
            ],
            parameters.maxAPR,
            parameters.proportion,
        )

    def __repr__(self):
        return f"EconomicModelSigmoid({self.offset}, {self.buckets}, {self.budget})"

    @property
    def print_prefix(self) -> str:
        return "EconomicModelSigmoid"
