from math import log, pow

from core.components.parameters import Parameters

from .budget import Budget


class Bucket:
    def __init__(self, name: str, flatness: float, skewness: float, upperbound: float):
        self.name = name
        self.flatness = flatness
        self.skewness = skewness
        self.upperbound = upperbound

    def apr(self, x: float):
        """
        Calculate the APR for the bucket.
        """
        try:
            return log(pow(self.upperbound / x, self.skewness) - 1) / self.flatness
        except ValueError as e:
            raise e
        except ZeroDivisionError as e:
            raise ValueError(e)
        except OverflowError as e:
            raise ValueError(e)

    @classmethod
    def fromParameters(cls, name: str, parameters: Parameters):
        return cls(
            name,
            parameters.flatness,
            parameters.skewness,
            parameters.upperbound,
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
        self.budget: Budget = None

    def apr(self, xs: list[float], max_apr: float = None):
        """
        Calculate the APR for the economic model.
        """
        apr = sum(b.apr(x) for b, x in zip(self.buckets, xs)) + self.offset

        if max_apr is not None:
            apr = min(apr, max_apr)

        return apr

    def message_count_for_reward(self, stake: float, xs: list[float]):
        """
        Calculate the message count for the reward.
        """
        apr = self.apr(xs, self.max_apr)

        rewards = apr / 100.0 / 12.0 * stake
        denominator = self.budget.ticket_price * self.budget.winning_probability

        return round(rewards / denominator * self.proportion)

    @classmethod
    def fromParameters(cls, parameters: Parameters):
        bucket_names = vars(parameters.buckets)

        return cls(
            parameters.offset,
            [
                Bucket.fromParameters(name, getattr(parameters.buckets, name))
                for name in bucket_names
            ],
            parameters.maxAPRPercentage,
            parameters.proportion,
        )

    def __repr__(self):
        return f"EconomicModel({self.offset}, {self.buckets}, {self.budget})"
