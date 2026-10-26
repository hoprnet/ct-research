import operator
import re
from typing import Optional

from core.types.balance import Balance

_METRIC_OPERATORS = (
    ("!=", operator.ne),
    (">=", operator.ge),
    ("<=", operator.le),
    ("==", operator.eq),
    (">", operator.gt),
    ("<", operator.lt),
)
_BALANCE_REPR_PATTERN = re.compile(r"^Balance\(_value=(.+)\)$")
_UNSUPPORTED_OPERATOR_PREFIXES = ("<>", "=>", "=<")


class Metric:
    def __init__(self, text: str, value: float, suffix: str = "", cdt: Optional[bool | str] = None):
        """
        Initialisation of the class.
        """

        self._text = text
        self._value = value
        self._suffix = suffix
        self._cdt = cdt

    @property
    def text(self) -> str:
        return self._text

    @property
    def value(self) -> float:
        return self._value

    @property
    def v(self) -> float:
        return self._value

    @property
    def suffix(self) -> str:
        return self._suffix

    @property
    def cdt(self) -> Optional[bool]:
        if self._cdt is None:
            return None
        if isinstance(self._cdt, str):
            return self._evaluate_condition(self._cdt)
        if isinstance(self._cdt, bool):
            return self._cdt

        raise TypeError("Condition must be a string or a boolean")

    def _evaluate_condition(self, condition: str) -> bool:
        text = condition.strip()
        if text.startswith(_UNSUPPORTED_OPERATOR_PREFIXES):
            raise ValueError(f"Unsupported metric condition: {condition}")
        for symbol, comparator in _METRIC_OPERATORS:
            if not text.startswith(symbol):
                continue
            rhs_text = text[len(symbol) :].strip()
            if not rhs_text or rhs_text[0] in "<>!=":
                raise ValueError(f"Unsupported metric condition: {condition}")
            rhs = self._coerce_condition_value(rhs_text)
            return comparator(self.value, rhs)

        raise ValueError(f"Unsupported metric condition: {condition}")

    def _coerce_condition_value(self, value: str):
        if isinstance(self.value, Balance):
            match = _BALANCE_REPR_PATTERN.match(value)
            if match:
                value = match.group(1)
            return Balance(value)

        if isinstance(self.value, bool):
            lowered = value.lower()
            if lowered in {"true", "yes", "on"}:
                return True
            if lowered in {"false", "no", "off"}:
                return False
            raise ValueError(f"Unsupported metric condition value: {value}")

        if isinstance(self.value, int) and not isinstance(self.value, bool):
            return int(value)

        if isinstance(self.value, float):
            return float(value)

        return type(self.value)(value)

    def print_line(self):
        if self.cdt is None:
            prefix = " "
        else:
            prefix = "✓" if self.cdt else "✗"

        value_format = "s" if isinstance(self.value, str) else "6.2f"

        print(
            f"{prefix} {self.text} {'.'*(30-len(self.text))}: "
            + f"{self.value:{value_format}} {self.suffix}"
        )

    def __repr__(self):
        return f"<Metric {self.text}={self.value} {self.suffix}>"
