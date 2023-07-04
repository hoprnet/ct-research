import json
import pytest
from unittest import mock
from economic_handler.economic_handler import EconomicHandler


@pytest.fixture(scope="module", autouse=True)
def file_contents():
    return {
        "parameters": {
            "first_parameter": {
                "value": 1,
                "comment": "some comment",
            },
            "second_parameter": {
                "value": 3,
                "comment": "some comment",
            },
            "third_parameter": {
                "value": 3,
                "comment": "some comment",
            },
            "fourth_parameter": {
                "value": -1,
                "comment": "some comment",
            },
        },
        "equations": {
            "first_equation": {
                "formula": "some formula",
                "condition": "some condition",
            },
            "second_equation": {
                "formula": "some other formula",
                "condition": "some other condition",
            },
        },
        "budget": {"value": 100, "comment": "some comment"},
    }


@pytest.fixture
def mock_open_file():
    with mock.patch("builtins.open") as mock_open_func:
        yield mock_open_func


@pytest.mark.asyncio
async def test_read_parameters_and_equations(mock_open_file, file_contents):
    """
    Test whether parameters, equations, and budget are correctly returned
    as a dictionary
    """
    mock_file = mock_open_file.return_value.__enter__.return_value
    mock_file.read.return_value = json.dumps(file_contents)

    node = EconomicHandler("some_url", "some_api_key", "some_rpch_endpoint")

    result = await node.read_parameters_and_equations(mock_file)

    assert isinstance(result[1], dict)
    assert isinstance(result[2], dict)
    assert isinstance(result[3], dict)


@pytest.mark.asyncio
async def test_read_parameters_and_equations_file_not_found():
    """
    Test whether an empty dictionary gets returned in case of a FileNotFoundError.
    """
    file_name = "non_existent_file.json"
    node = EconomicHandler("some_url", "some_api_key", "some_rpch_endpoint")

    result = await node.read_parameters_and_equations(file_name)

    assert result == ("params", {}, {}, {})


@pytest.mark.asyncio
async def test_read_parameters_and_equations_check_values(
    mock_open_file, file_contents
):
    """
    Test whether an empty dictionary gets returned in case of a ValidationError.
    """
    mock_file = mock_open_file.return_value.__enter__.return_value
    mock_file.read.return_value = json.dumps(file_contents)

    node = EconomicHandler("some_url", "some_api_key", "some_rpch_endpoint")

    result = await node.read_parameters_and_equations(mock_file)

    assert result == ("params", {}, {}, {})
