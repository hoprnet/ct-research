from core.components.parameters import Parameters
from prometheus_client import Gauge

BUDGET_PERIOD = Gauge("budget_period", "Budget period for the economic model")
DISTRIBUTIONS_PER_PERIOD = Gauge("dist_freq", "Number of expected distributions")
TICKET_PRICE = Gauge("ticket_price", "Ticket price")
TICKET_WINNING_PROB = Gauge("ticket_winning_prob", "Ticket winning probability")


class Budget:
    def __init__(
        self,
        period: float,
        distribution_per_period: float,
        ticket_price: float,
        winning_probability: float,
    ):
        self.period = period
        self.distribution_per_period = distribution_per_period
        self.ticket_price = ticket_price
        self.winning_probability = winning_probability

    @property
    def period(self):
        return self._period

    @property
    def distribution_per_period(self):
        return self._distribution_per_period

    @property
    def ticket_price(self):
        return self._ticket_price

    @property
    def winning_probability(self):
        return self._winning_probability

    @period.setter
    def period(self, value):
        self._period = value
        BUDGET_PERIOD.set(value)

    @distribution_per_period.setter
    def distribution_per_period(self, value):
        self._distribution_per_period = value
        DISTRIBUTIONS_PER_PERIOD.set(value)

    @ticket_price.setter
    def ticket_price(self, value):
        self._ticket_price = value
        TICKET_PRICE.set(value)

    @winning_probability.setter
    def winning_probability(self, value):
        self._winning_probability = value
        TICKET_WINNING_PROB.set(value)

    @classmethod
    def fromParameters(cls, parameters: Parameters):
        return cls(
            parameters.period,
            parameters.countsInPeriod,
            parameters.ticketPrice,
            parameters.winningProbability,
        )

    @property
    def delay_between_distributions(self):
        return self.period / self.distribution_per_period
