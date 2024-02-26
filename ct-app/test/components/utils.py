import os
from contextlib import contextmanager


@contextmanager
def handle_envvars(**kwargs):
    for key, value in kwargs.items():
        os.environ[key.upper()] = value

    try:
        yield
    finally:
        for key in kwargs.keys():
            del os.environ[key.upper()]
