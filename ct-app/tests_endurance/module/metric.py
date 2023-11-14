class Metric:
    def __init__(
        self, text: str, value: float, suffix: str = "", cdt: bool or str = None
    ):
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
    def cdt(self) -> bool:
        if self._cdt is None:
            return None
        if isinstance(self._cdt, str):
            return eval(f"{self.value} {self._cdt}")
        if isinstance(self._cdt, bool):
            return self._cdt

        raise TypeError("Condition must be a string or a boolean")

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
