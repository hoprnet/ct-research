from typing import Any

from core.components.balance import Balance


def convert_unit(value: Any):
    if value is None:
        return None

    if isinstance(value, Balance):
        return value

    try:
        value = Balance(value)
    except TypeError:
        pass
    else:
        return value

    try:
        value = float(value)
    except ValueError:
        pass
    except TypeError:
        pass

    try:
        integer = int(value)
        if integer == value:
            value = integer

    except ValueError:
        pass
    except TypeError:
        pass

    return value
