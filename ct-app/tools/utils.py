import json
import logging
import logging.config
import os
import sys

import jsonschema

from .logger import ColoredLogger


def getlogger() -> logging.Logger:
    """
    Generate a logger instance based on folder and name.
    :returns: a tuple with the logger instance and the name of the log file
    """
    # configure and get logger handler
    module = running_module(uppercase=True)
    if not module:
        module = "main"

    # checks if a logger already exists with the given module name
    logging.getLogger("httpx").setLevel(logging.WARNING)  # logs were flooded by httpx
    logging.getLogger("swagger_client.rest").setLevel(logging.WARNING)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)

    if logging.getLoggerClass() != ColoredLogger:
        logging.setLoggerClass(ColoredLogger)

    logger = logging.getLogger(module)
    logger.setLevel(logging.INFO)

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
    log = getlogger()
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


def running_module(uppercase: bool = False):
    """
    Retrieve the name of the module that is running, independently of the file that
    calls this method.
    :param uppercase: if True, the module name will be returned in uppercase
    :returns: the name of the module that is running"""
    argv = sys.argv[0]

    if not argv.endswith("__main__.py"):
        return None

    module = argv.split("/")[-2]

    if uppercase:
        module = module.upper()

    return module
