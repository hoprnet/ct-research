from os import environ


class Flags:
    @classmethod
    def get_environment_flags(cls, prefix: str = "FLAG_"):
        """
        Get all environment variable starting with a given prefix.
        """
        flags = [key for key in environ.keys() if key.startswith(prefix)]
        return [item.replace(prefix, "").lower() for item in flags]
