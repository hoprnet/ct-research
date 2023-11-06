class RewardEntry:
    def __init__(self, node_address: str, safe_address: str = None, reward: float = 0):
        self.node_address = node_address
        self.safe_address = safe_address
        self.reward = reward

    @property
    def in_network(self):
        return self.safe_address is not None

    def __repr__(self) -> str:
        return f"RewardEntry({self.node_address}, {self.reward}, {self.safe_address})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RewardEntry):
            return False

        return self.node_address == other.node_address

    def __add__(self, other: object) -> object:
        if not isinstance(other, RewardEntry):
            return NotImplemented

        if self.node_address != other.node_address:
            return NotImplemented

        self.reward += other.reward
        return self

    def __hash__(self) -> int:
        return hash(self.node_address)
