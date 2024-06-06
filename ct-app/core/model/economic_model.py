from core.components.parameters import Parameters
from prometheus_client import Gauge

BUDGET = Gauge("budget", "Budget for the economic model")
BUDGET_PERIOD = Gauge("budget_period", "Budget period for the economic model")
DISTRIBUTIONS_PER_PERIOD = Gauge("dist_freq", "Number of expected distributions")
TICKET_PRICE = Gauge("ticket_price", "Ticket price")
TICKET_WINNING_PROB = Gauge("ticket_winning_prob", "Ticket winning probability")


class Equation:
    def __init__(self, formula: str, condition: str):
        self.formula = formula
        self.condition = condition

    @classmethod
    def fromParameters(cls, parameters: Parameters):
        return cls(parameters.formula, parameters.condition)

class Equations:
    def __init__(self, f_x: Equation, g_x: Equation):
        self.f_x = f_x
        self.g_x = g_x

    @classmethod
    def fromParameters(cls, parameters: Parameters):
        return cls(
            Equation.fromParameters(parameters.fx),
            Equation.fromParameters(parameters.gx),
        )


class Coefficients:
    def __init__(self, a: float, b: float, c: float, l: float):  # noqa: E741
        self.a = a
        self.b = b
        self.c = c
        self.l = l

    @classmethod
    def fromParameters(cls, parameters: Parameters):
        return cls(
            parameters.a,
            parameters.b,
            parameters.c,
            parameters.l,
        )


class Budget:
    def __init__(
        self,
        amount: float,
        period: float,
        s: float,
        distribution_per_period: float,
        winning_probability: float,
    ):
        self.amount = amount
        self.period = period
        self.s = s
        self.distribution_per_period = distribution_per_period
        self.winning_probability = winning_probability
        self.ticket_price = None

    @property
    def amount(self):
        return self._amount

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

    @amount.setter
    def amount(self, value):
        self._amount = value
        BUDGET.set(value)

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
        if value is not None:
            TICKET_PRICE.set(value)

    @winning_probability.setter
    def winning_probability(self, value):
        self._winning_probability = value
        TICKET_WINNING_PROB.set(value)
    
    @classmethod
    def fromParameters(cls, parameters: Parameters):
        return cls(
            parameters.amount,
            parameters.period,
            parameters.s,
            parameters.countsInPeriod,
            parameters.winningProbability,
        )

    @property
    def delay_between_distributions(self):
        return self.period / self.distribution_per_period


class EconomicModel:
    def __init__(
        self, equations: Equations, coefficients: Coefficients, budget: Budget
    ):
        """
        Initialisation of the class.
        """
        self.equations = equations
        self.coefficients = coefficients
        self.budget = budget

    def transformed_stake(self, stake: float):
        func = self.equations.f_x

        # convert parameters attribute to dictionary
        kwargs = vars(self.coefficients)
        kwargs.update({"x": stake})

        if not eval(func.condition, kwargs):
            func = self.equations.g_x

        return eval(func.formula, kwargs)

    @property
    def delay_between_distributions(self):
        return self.budget.delay_between_distributions

    @classmethod
    def fromParameters(cls, parameters: Parameters):
        return EconomicModel(
            Equations.fromParameters(parameters.equations), 
            Coefficients.fromParameters(parameters.coefficients), 
            Budget.fromParameters(parameters.budget),
        )
    
    def __repr__(self):
        return f"EconomicModel({self.equations}, {self.coefficients}, {self.budget})"
