import random
import string
from os import environ


class Utils:
    @classmethod
    def random_string(cls, length: int, alpha: bool = True, numeric: bool = True):
        choices = ""
        if alpha:
            choices += string.ascii_letters
        if numeric:
            choices += string.digits

        return "".join(random.choices(choices, k=length))

    @classmethod
    def envvar(cls, var_name, default=None, type=str):
        if var_name in environ:
            return type(environ[var_name])
        else:
            return default
