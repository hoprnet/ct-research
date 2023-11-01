import random
import string


def random_string(length: int, alpha: bool = True, numeric: bool = True):
    choices = ""
    if alpha:
        choices += string.ascii_letters
    if numeric:
        choices += string.digits

    return "".join(random.choices(choices, k=length))
