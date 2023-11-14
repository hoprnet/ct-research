from pandas import Series, DataFrame
from .entry import Entry


class DuneEntry(Entry):
    def __init__(
        self,
        date: str,
        safe_address: str,
        deployment_tx_hash: str,
        wxHOPR_balance: float,
        nr_nft: bool,
        nft_id: int,
    ):
        self.date = date
        self.node_address = ""
        self.safe_address = safe_address
        self.deployment_tx_hash = deployment_tx_hash
        self.wxHOPR_balance = wxHOPR_balance
        self.nr_nft = nr_nft
        self.nft_id = nft_id

    @property
    def safe_address(self) -> str:
        return self._safe_address

    @safe_address.setter
    def safe_address(self, value: str):
        self._safe_address = value.strip().lower()

    @property
    def node_address(self) -> str:
        return self._node_address

    @node_address.setter
    def node_address(self, value: str):
        self._node_address = value.strip().lower()

    def _toPandaSerie(self):
        return Series(
            {
                value: getattr(self, key)
                for key, value in self._import_keys_and_values().items()
            }
        )

    def __repr__(self):
        return (
            "DuneEntry("
            + f"{self.safe_address}, "
            + f"{self.deployment_tx_hash}, "
            + f"{self.wxHOPR_balance}, "
            + f"{self.nr_nft},"
        )

    @classmethod
    def toDataFrame(cls, entries: list["DuneEntry"]):
        return DataFrame([entry._toPandaSerie() for entry in entries])

    @classmethod
    def _import_keys_and_values(self) -> dict[str, str]:
        return {
            "date": "deployment_date",
            "safe_address": "safe_address",
            "node_address": "node_address",
            "deployment_tx_hash": "deployment_tx_hash",
            "wxHOPR_balance": "wxHOPR_balance",
            "nr_nft": "nr_nft",
            "nft_id": "nft_id",
        }
