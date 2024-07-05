from core.components.parameters import Parameters

from .budget import Budget


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


class EconomicModelLegacy:
    def __init__(
        self,
        equations: Equations,
        coefficients: Coefficients,
        proportion: float,
        apr: float,
    ):
        """
        Initialisation of the class.
        """
        self.equations = equations
        self.coefficients = coefficients
        self.proportion = proportion
        self.apr = apr
        self.budget: Budget = Budget()

    def transformed_stake(self, stake: float):
        # convert parameters attribute to dictionary
        kwargs = vars(self.coefficients)
        kwargs.update({"x": stake})

        for func in vars(self.equations).values():
            if eval(func.condition, kwargs):
                break
        else:
            return 0

        return eval(func.formula, kwargs)

    def message_count(self, stake: float, redeemed_rewards: float = 0):
        """
        Calculate the yearly message count for the reward.
        """
        self.coefficients.l += redeemed_rewards
        rewards = self.apr * self.transformed_stake(stake) / 100
        self.coefficients.l -= redeemed_rewards

        under = self.budget.ticket_price * self.budget.winning_probability

        return round(rewards / under * self.proportion) if under != 0 else 0

    @classmethod
    def fromParameters(cls, parameters: Parameters):
        return cls(
            Equations.fromParameters(parameters.equations),
            Coefficients.fromParameters(parameters.coefficients),
            parameters.proportion,
            parameters.apr,
        )

    def __repr__(self):
        return (
            f"EconomicModelLegacy({self.equations}, {self.coefficients}, {self.budget})"
        )
