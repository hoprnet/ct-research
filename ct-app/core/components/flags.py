from os import environ


class Flags:
    _cache_flags = None
    global_prefix = "FLAG_"

    @classmethod
    def get_environment_flag_value(cls, methodname: str, prefix: str):
        """
        Get the value of an environment variable starting with a given prefix.
        """
        _prefix = cls.global_prefix + prefix

        return float(environ.get(f"{_prefix}{methodname.upper()}", None))

    @classmethod
    def get_environment_flags(cls, prefix: str):
        """
        Get all environment variable starting with a given prefix.
        """

        if cls._cache_flags is None:
            cls._cache_flags = [
                key for key in environ.keys() if key.startswith(cls.global_prefix)
            ]

        _prefix = cls.global_prefix + prefix
        return [item.replace(_prefix, "").lower() for item in cls._cache_flags]
