from os import environ


class Flags:
    flags = []

    @classmethod
    def get_environment_flags(cls, prefix: str = "FLAG_"):
        """
        Get all environment variable starting with a given prefix.
        """

        if not cls.flags:
            flags = [key for key in environ.keys() if key.startswith(prefix)]
            cls.flags = [item.replace(prefix, "").lower() for item in flags]

        return cls.flags
