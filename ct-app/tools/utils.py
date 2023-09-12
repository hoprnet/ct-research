import asyncio
import csv
import json
import logging
import logging.config
import os
import sys

import jsonschema
from aiohttp.client import ClientSession
from aiohttp.client_exceptions import InvalidURL
from google.cloud import storage

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

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("hoprd_sdk.rest").setLevel(logging.WARNING)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
    logging.getLogger("urllib3.util.retry").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.orm.mapper.Mapper").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool.impl.QueuePool").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.orm.path_registry").setLevel(logging.WARNING)

    # checks if a logger already exists with the given module name
    logging.setLoggerClass(ColoredLogger)

    logger = logging.getLogger(module)
    logger.setLevel(logging.DEBUG)

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


def running_module(uppercase: bool = False):
    """
    Retrieve the name of the module that is running, independently of the file that
    calls this method.
    :param uppercase: if True, the module name will be returned in uppercase
    :returns: the name of the module that is running"""
    argv = sys.argv[0]

    print(sys.argv)

    if not argv.endswith("__main__.py"):
        return None

    module = argv.split("/")[-2]

    if uppercase:
        module = module.upper()

    return module


async def post_dictionary(url: str, data: dict, retry_sleep: int = None):
    """
    Sends a JSON to the given URL. If the transmission fails, it will retry after the
    given delay.
    :param session: the aiohttp session
    :param url: the URL to send the JSON to
    :param data: the JSON to send
    :param retry_sleep: the delay (in seconds) to wait before retrying to send the JSON.
    If not set, no retry will be performed
    :returns: True if the JSON was sent successfully, False otherwise
    """

    async def _post(session: ClientSession, url: str, data: dict):
        try:
            async with session.post(url, json=data) as response:
                if response.status == 200:
                    return True
                log.error(f"{response}")
        except InvalidURL:
            log.exception("Invalid URL")
        except Exception:  # ClientConnectorError
            log.exception("Error transmitting dictionary")

        return False

    log = getlogger()

    async with ClientSession() as session:
        success = await _post(session, url, data)

        if not success and retry_sleep:
            await asyncio.sleep(retry_sleep)
            await _post(session, url, data)

    return success


def write_csv_on_gcp(bucket_name: str, blob_name: str, data: list[str]):
    """
    Write a blob from GCS using file-like IO
    :param bucket_name: The name of the bucket
    :param blob_name: The name of the blob
    :param data: The data to write
    """
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    with blob.open("w") as f:
        writer = csv.writer(f)
        writer.writerows(data)


def read_json_on_gcp(bucket_name, blob_name, schema=None):
    """
    Reads a JSON file and validates its contents using a schema.
    :param: bucket_name: The name of the bucket
    :param: blob_name: The name of the blob
    ;param: schema (opt): The validation schema
    :returns: (dict): The contents of the JSON file.
    """
    log = getlogger()

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    with blob.open("r") as f:
        contents = json.load(f)

    if schema is not None:
        try:
            jsonschema.validate(
                contents,
                schema=schema,
            )
        except jsonschema.ValidationError as e:
            log.exception(
                f"The file in'{blob_name}' does not follow the expected structure. {e}"
            )
            return {}

    return contents
