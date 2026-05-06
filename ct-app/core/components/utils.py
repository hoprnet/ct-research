import os

from ..types.balance import Balance


class Utils:
    @classmethod
    async def balanceInChannels(cls, channels: list) -> dict[str, Balance]:
        """
        Returns a dict containing all unique saddress-balance links.
        :param channels: The list of channels.
        :returns: A dict containing all address-balance links.
        """

        results: dict[str, Balance] = {}
        for c in channels:
            if not (hasattr(c, "source") and hasattr(c, "status") and hasattr(c, "balance")):
                continue

            if not c.status.is_open:
                continue

            if c.source not in results:
                results[c.source] = Balance.zero("wxHOPR")

            results[c.source] += c.balance

        return results


class EnvironmentUtils:
    @classmethod
    def envvar(cls, name: str, type=str, default=None):
        value = os.getenv(name)
        if value is None:
            return default

        if type is bool:
            return value.strip().lower() in {"1", "true", "yes", "on"}

        return type(value)
