from .baseclass import Base
from .environment_utils import EnvironmentUtils


class Parameters(Base):
    """
    Class that represents a set of parameters that can be accessed and modified. The parameters are stored in a dictionary and can be accessed and modified using the dot notation. The parameters can be loaded from environment variables with a specified prefix.
    """

    def __init__(self):
        super().__init__()

    def __call__(self, *prefixes: str or list[str]):
        """
        Load the parameters from the environment variables with the specified prefixes. The parameters will be stored in the instance with the name of the prefix in lowercase. If the prefix ends with an underscore, the underscore will be removed. The parameters will be stored in a new instance of the Parameters class.

        :param prefixes: The prefixes of the environment variables to load the parameters from.
        """
        for prefix in prefixes:
            subparams = type(self)()

            subparams_name = prefix.lower()
            if subparams_name[-1] == "_":
                subparams_name = subparams_name[:-1]

            for key, value in EnvironmentUtils.envvarWithPrefix(prefix).items():
                k = key.replace(prefix, "").lower()

                try:
                    value = float(value)
                except ValueError:
                    pass

                try:
                    integer = int(value)
                    if integer == value:
                        value = integer
                except ValueError:
                    pass

                setattr(subparams, k, value)

            setattr(self, subparams_name, subparams)

        return self
