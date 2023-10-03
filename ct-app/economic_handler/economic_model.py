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

    @classmethod
    def from_dictionary(cls, _input: dict):
        budget = _input.get("budget", {}).get("value", None)
        period = _input.get("budget_period", {}).get("value", None)
        s = _input.get("s", {}).get("value", None)
        distribution_frequency = _input.get("dist_freq", {}).get("value", None)
        ticket_price = _input.get("ticket_price", {}).get("value", None)
        winning_probability = _input.get("winning_prob", {}).get("value", None)

        cls(
            budget, period, s, distribution_frequency, ticket_price, winning_probability
        )


class EconomicModel:
    """Class description."""

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

    @classmethod
    def from_dictionary(cls, _input: dict):
        equations = Equations.from_dictionary(_input.get("equations", {}))
        parameters = Parameters.from_dictionary(_input.get("parameters", {}))
        budget = BudgetParameters.from_dictionary(_input.get("budget_param", {}))

        return cls(equations, parameters, budget)
