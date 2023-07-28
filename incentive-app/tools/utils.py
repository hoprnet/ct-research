import logging
import os
import logging.config
import jsonschema
import json


def _getlogger() -> logging.Logger:
    """
    Generate a logger instance based on folder and name.
    :returns: a tuple with the logger instance and the name of the log file
    """

    # configure and get logger handler
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s:%(asctime)s:%(message)s"
    )

    logger = logging.getLogger(__name__)
    logging.getLogger("httpx").setLevel(logging.WARNING)  # logs were flooded by httpx

    return logger


def envvar(name: str, type: type = None) -> str:
    """
    Gets the string contained in environment variable 'name' and casts it to 'type'.
    :param name: name of the environment variable
    :param type: type to cast the variable to
    :returns: the string contained in the environment variable
    :raises ValueError: if the environment variable is not found
    """
    if os.getenv(name) is None:
        raise ValueError(f"Environment variable [{name}] not found")

    value = os.getenv(name)

    if type:
        return type(value)

    return value


def read_json_file(path, schema):
    """
    Reads a JSON file and validates its contents using a schema.
    :param: path: The path to the parameters file
    ;param: schema: The validation schema
    :returns: (dict): The contents of the JSON file.
    """
    log = _getlogger()
    try:
        with open(path, "r") as file:
            contents = json.load(file)
    except FileNotFoundError as e:
        log.exception(f"The file in '{path}' does not exist. {e}")
        return {}

    try:
        jsonschema.validate(
            contents,
            schema=schema,
        )
    except jsonschema.ValidationError as e:
        log.exception(
            f"The file in'{path}' does not follow the expected structure. {e}"
        )
        return {}

    return contents
