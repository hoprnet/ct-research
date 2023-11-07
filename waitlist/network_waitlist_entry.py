from .entry import Entry


class NetworkWaitlistEntry(Entry):
    def __init__(
        self,
        id: str,
        safe_address: str,
        eligibility: str,
    ):
        self.id = id
        self.safe_address = safe_address
        self.eligibility = eligibility

    @property
    def id(self) -> str:
        return self._id

    @id.setter
    def id(self, value: str):
        try:
            int(value)
        except TypeError:
            self._id = None
        else:
            self._id = int(value)

    @property
    def safe_address(self) -> str:
        return self._safe_address

    @safe_address.setter
    def safe_address(self, value: str):
        if not isinstance(value, str):
            self._safe_address = None
        else:
            self._safe_address = value.strip().lower()

    @property
    def eligibility(self) -> str:
        return self._eligibility

    @eligibility.setter
    def eligibility(self, value: str):
        try:
            self._eligibility = value.strip().lower()
        except AttributeError:
            self._eligibility = None

    @property
    def eligible(self) -> bool:
        return self.eligibility == "yes"

    def __repr__(self):
        return str(self)

    @classmethod
    def _import_keys_and_values(self) -> dict[str, str]:
        return {
            "id": "Waitlist No.",
            "safe_address": "Safe address",
            "eligibility": "Eligibility",
        }
