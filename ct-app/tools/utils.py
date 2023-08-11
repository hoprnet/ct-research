import json
import logging
import logging.config
import os
import sys
from aiohttp.client import ClientSession

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
    if logging.getLoggerClass() != ColoredLogger:
        logging.setLoggerClass(ColoredLogger)
        logging.getLogger("httpx").setLevel(
            logging.WARNING
        )  # logs were flooded by httpx

    return logging.getLogger(module)


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


async def post_dictionary(session: ClientSession, url: str, data: dict):
    """
    Sends a JSON to the given URL.
    :param session: the aiohttp session
    :param url: the URL to send the JSON to
    :param data: the JSON to send
    :returns: True if the JSON was sent successfully, False otherwise
    """
    log = getlogger()

    try:
        async with session.post(url, json=data) as response:
            if response.status == 200:
                return True
            log.error(f"{response}")
    except Exception:  # ClientConnectorError
        log.exception("Error transmitting dictionary")

    return False
