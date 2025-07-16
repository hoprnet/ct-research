from dataclasses import dataclass
from decimal import Decimal

import pytest
import yaml

from core.components.balance import Balance
from core.components.config_parser.base_classes import ExplicitParams

param_dict: str = """
        foo: foo_value
        bar: 42
        sub_param:
            baz: 3.14
    """


@dataclass(init=False)
class SubParameter(ExplicitParams):
    baz: float


@dataclass(init=False)
class Parameters(ExplicitParams):
    foo: str
    bar: int
    sub_param: SubParameter


def test_parameter_parsing():
    config: dict = yaml.safe_load(param_dict)

    params = Parameters(config)

    assert isinstance(params.foo, str) and params.foo == "foo_value"
    assert isinstance(params.bar, int) and params.bar == 42
    assert hasattr(params, "sub_param") and isinstance(params.sub_param, ExplicitParams)
    assert isinstance(params.sub_param.baz, float) and params.sub_param.baz == 3.14


def test_wrong_type():
    input: str = """
        foo: foo_value
        bar: not_an_int
        sub_param:
            baz: 3.14
    """

    config: dict = yaml.safe_load(input)
    with pytest.raises(ValueError):
        Parameters(config)


def test_parameter_as_dict():
    config: dict = yaml.safe_load(param_dict)

    params = Parameters(config)

    assert params.as_dict() == config


def test_verify_parameters():
    config: dict = yaml.safe_load(param_dict)

    assert Parameters.verify(config) is True

    config["new"] = "new"
    assert Parameters.verify(config) is True

    config.pop("foo")
    with pytest.raises(KeyError):
        Parameters.verify(config) is False

    with pytest.raises(KeyError):
        Parameters.verify({}) is False


def test_verify_parameters_type():
    config: dict = yaml.safe_load(param_dict)
    config["bar"] = "should be an int"

    with pytest.raises(ValueError):
        Parameters.verify(config)


def test_generate():
    @dataclass(init=False)
    class SubParameter(ExplicitParams):
        baz: float

    @dataclass(init=False)
    class CustomParameters(ExplicitParams):
        foo: str
        bar: int
        baz: dict
        boo: list[int]
        balance: Balance
        decimal: Decimal
        sub_param: SubParameter

    assert CustomParameters(CustomParameters.generate())
