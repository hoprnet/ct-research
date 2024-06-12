from packaging.version import Version

from .address import Address


class Peer:
    """
    Representation of a peer in the network. A peer is a node that is part of the network and not hosted by HOPR.
    """

    def __init__(self, id: str, address: str, version: str):
        """
        Create a new Peer with the specified id, address and version. The id refers to the peerId, the address refers to the native address of a node.
        :param id: The peer's peerId
        :param address: The peer's native address
        :param version: The reported peer's version
        """
        self.address = Address(id, address)
        self.version = version
        self.channel_balance = None

        self.safe_address = None
        self.safe_balance = None
        self.safe_allowance = None

        self._safe_address_count = None

    def version_is_old(self, min_version: str or Version) -> bool:
        """
        Check if the peer's version is older than the specified version.
        :param min_version: The minimum version to check against.
        """
        if isinstance(min_version, str):
            min_version = Version(min_version)

        return self.version < min_version

    @property
    def version(self) -> Version:
        return self._version

    @version.setter
    def version(self, value: str or Version):
        if not isinstance(value, Version):
            try:
                value = Version(value)
            except Exception:
                value = Version("0.0.0")

        self._version = value

    @property
    def node_address(self) -> str:
        return self.address.address

    @property
    def safe_address_count(self) -> int:
        if self._safe_address_count is None:
            self.safe_address_count = 1

        return self._safe_address_count

    @safe_address_count.setter
    def safe_address_count(self, value: int):
        self._safe_address_count = value

    @property
    def split_stake(self) -> float:
        if self.safe_balance is None:
            raise ValueError("Safe balance not set")
        if self.channel_balance is None:
            raise ValueError("Channel balance not set")
        if self.safe_address_count is None:
            raise ValueError("Safe address count not set")

        return float(self.safe_balance) / float(self.safe_address_count) + float(
            self.channel_balance
        )

    @property
    def has_low_stake(self) -> bool:
        if self.economic_model is None:
            raise ValueError("Economic model not set")

        return self.split_stake < self.economic_model.coefficients.l

    @property
    def transformed_stake(self) -> float:
        if self.economic_model is None:
            raise ValueError("Economic model not set")

        return self.economic_model.transformed_stake(self.split_stake)

    @classmethod
    def attributesToExport(cls):
        return [
            "node_address",
            "channel_balance",
            "safe_address",
            "safe_balance",
            "safe_address_count",
            "split_stake",
        ]

    @classmethod
    def toCSV(cls, peers: list) -> list[list[str]]:
        attributes = Peer.attributesToExport()
        lines = [["peer_id"] + attributes]

        for peer in peers:
            line = [peer.address.id] + [getattr(peer, attr) for attr in attributes]
            lines.append(line)

        return lines

    def __repr__(self):
        return f"Peer(address: {self.address})"

    def __eq__(self, other):
        return self.address == other.address

    def __hash__(self):
        return hash(self.address)
