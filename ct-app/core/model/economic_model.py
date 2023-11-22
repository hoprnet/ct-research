import os

from prometheus_client import Gauge

from core.components.utils import Utils

BUDGET = Gauge("budget", "Budget for the economic model")
BUDGET_PERIOD = Gauge("budget_period", "Budget period for the economic model")
DISTRIBUTION_FREQUENCY = Gauge("dist_freq", "Number of expected distributions")
TICKET_PRICE = Gauge("ticket_price", "Ticket price")
TICKET_WINNING_PROB = Gauge("ticket_winning_prob", "Ticket winning probability")


class Equation:
    def __init__(self, formula: str, condition: str):
        self.formula = formula
        self.condition = condition

    @classmethod
    def from_dictionary(cls, _input: dict):
        formula = _input.get("formula", "")
        condition = _input.get("condition", "")

        return cls(formula, condition)


class Equations:
    def __init__(self, f_x: Equation, g_x: Equation):
        self.f_x = f_x
        self.g_x = g_x

    @classmethod
    def from_dictionary(cls, _input: dict):
        f_x = Equation.from_dictionary(_input.get("f_x", {}))
        g_x = Equation.from_dictionary(_input.get("g_x", {}))

        return cls(f_x, g_x)


class Parameters:
    def __init__(self, a: float, b: float, c: float, l: float):  # noqa: E741
        self.a = a
        self.b = b
        self.c = c
        self.l = l

    @classmethod
    def from_dictionary(cls, _input: dict):
        a = _input.get("a", {}).get("value", None)
        b = _input.get("b", {}).get("value", None)
        c = _input.get("c", {}).get("value", None)
        l = _input.get("l", {}).get("value", None)  # noqa: E741

        return cls(a, b, c, l)


class BudgetParameters:
    def __init__(
        self,
        budget: float,
        period: float,
        s: float,
        distribution_frequency: float,
        ticket_price: float,
        winning_probability: float,
    ):
        self.budget = budget
        self.period = period
        self.s = s
        self.distribution_frequency = distribution_frequency
        self.ticket_price = ticket_price
        self.winning_probability = winning_probability

    @property
    def budget(self):
        return self._budget

    @property
    def period(self):
        return self._period

    @property
    def distribution_frequency(self):
        return self._distribution_frequency

    @property
    def ticket_price(self):
        return self._ticket_price

    @property
    def winning_probability(self):
        return self._winning_probability

    @budget.setter
    def budget(self, value):
        self._budget = value
        BUDGET.set(value)

    @period.setter
    def period(self, value):
        self._period = value
        BUDGET_PERIOD.set(value)

    @distribution_frequency.setter
    def distribution_frequency(self, value):
        self._distribution_frequency = value
        DISTRIBUTION_FREQUENCY.set(value)

    @ticket_price.setter
    def ticket_price(self, value):
        self._ticket_price = value
        TICKET_PRICE.set(value)

    @winning_probability.setter
    def winning_probability(self, value):
        self._winning_probability = value
        TICKET_WINNING_PROB.set(value)

    @classmethod
    def from_dictionary(cls, _input: dict):
        budget = _input.get("budget", {}).get("value", None)
        period = _input.get("budget_period", {}).get("value", None)
        s = _input.get("s", {}).get("value", None)
        distribution_frequency = _input.get("dist_freq", {}).get("value", None)
        ticket_price = _input.get("ticket_price", {}).get("value", None)
        winning_probability = _input.get("winning_prob", {}).get("value", None)

        return cls(
            budget, period, s, distribution_frequency, ticket_price, winning_probability
        )

    @property
    def delay_between_distributions(self):
        return self.period / self.distribution_frequency


class EconomicModel:
    def __init__(
        self, equations: Equations, parameters: Parameters, budget: BudgetParameters
    ):
        """
        Initialisation of the class.
        """
        self.equations = equations
        self.parameters = parameters
        self.budget = budget

    def transformed_stake(self, stake: float):
        func = self.equations.f_x

        # convert parameters attribute to dictionary
        kwargs = vars(self.parameters)
        kwargs.update({"x": stake})

        if not eval(func.condition, kwargs):
            func = self.equations.g_x

        return eval(func.formula, kwargs)

    @property
    def delay_between_distributions(self):
        return self.budget.delay_between_distributions

    @classmethod
    def fromDict(cls, _input: dict):
        equations = Equations.from_dictionary(_input.get("equations"))
        parameters = Parameters.from_dictionary(_input.get("parameters"))
        budget = BudgetParameters.from_dictionary(_input.get("budget_param"))

        return cls(equations, parameters, budget)

    @classmethod
    def fromGCPFile(cls, bucket: str, filename: str):
        """
        Reads parameters and equations from a JSON file and validates it using a schema.
        :param: filename (str): The name of the JSON file containing the parameters
        and equations.
        :returns: EconomicModel: Instance containing the model parameters,equations,
        budget parameters.
        """
        parameters_file_path = os.path.join("assets", filename)

        contents = Utils.jsonFromGCP(bucket, parameters_file_path, None)

        return EconomicModel.fromDict(contents)

    def __repr__(self):
        return f"EconomicModel({self.equations}, {self.parameters}, {self.budget})"
