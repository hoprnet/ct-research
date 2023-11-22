from .address import Address


class Peer:
    def __init__(self, id: str, address: str):
        self.address = Address(id, address)
        self.channel_balance = None

        self.safe_address = None
        self.safe_balance = None

        self._safe_address_count = None

        self.economic_model = None
        self.reward_probability = None

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
    def transformed_stake(self) -> float:
        if self.economic_model is None:
            raise ValueError("Economic model not set")

        return self.economic_model.transformed_stake(self.split_stake)

    @property
    def total_balance(self) -> float:
        if self.safe_balance is None:
            raise ValueError("Safe balance not set")
        if self.channel_balance is None:
            raise ValueError("Channel balance not set")

        return float(self.channel_balance) + float(self.safe_balance)

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

        return self.split_stake < self.economic_model.parameters.l

    @property
    def expected_reward(self):
        if self.economic_model is None:
            raise ValueError("Economic model not set")
        if self.reward_probability is None:
            raise ValueError("Reward probability not set")

        return self.reward_probability * self.economic_model.budget.budget

    @property
    def airdrop_reward(self):
        if self.economic_model is None:
            raise ValueError("Economic model not set")

        return self.expected_reward * (1 - self.economic_model.budget.s)

    @property
    def protocol_reward(self):
        if self.economic_model is None:
            raise ValueError("Economic model not set")

        return self.expected_reward * self.economic_model.budget.s

    @property
    def protocol_reward_per_distribution(self):
        if self.economic_model is None:
            raise ValueError("Economic model not set")

        return self.protocol_reward / self.economic_model.budget.distribution_frequency

    @property
    def message_count_for_reward(self):
        if self.economic_model is None:
            raise ValueError("Economic model not set")

        budget = self.economic_model.budget
        denominator = budget.ticket_price * budget.winning_probability

        return round(self.protocol_reward_per_distribution / denominator)

    @property
    def apr_percentage(self):
        if self.economic_model is None:
            raise ValueError("Economic model not set")

        seconds_in_year = 60 * 60 * 24 * 365
        period = self.economic_model.budget.period

        return (
            (self.expected_reward * (seconds_in_year / period)) / self.split_stake
        ) * 100

    @property
    def complete(self) -> bool:
        # check that none of the attributes are None
        return all(
            [
                self.address,
                self.channel_balance,
                self.safe_address,
                self.safe_balance,
            ]
        )

    @classmethod
    def attributesToExport(cls):
        return [
            "node_address",
            "channel_balance",
            # "node_peer_ids",
            "safe_address",
            "safe_balance",
            "total_balance",
            "safe_address_count",
            "split_stake",
            "transformed_stake",
            "apr_percentage",
            "expected_reward",
            "airdrop_reward",
            "protocol_reward",
            "protocol_reward_per_distribution",
            "message_count_for_reward",
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