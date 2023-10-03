from .economic_model import EconomicModel


class Peer:
    def __init__(self, id, address, balance):
        self.id = id
        self.address = address
        self.channel_balance = balance

        self.node_ids = None
        self.safe_address = None
        self.safe_balance = None

        self.safe_address_count = None

        self.economic_model: EconomicModel = None
        self.reward_probability = None

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

        return self.protocol_reward_per_distribution / denominator

    @property
    def apy_percentage(self):
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
                self.id,
                self.address,
                self.channel_balance,
                self.node_ids,
                self.safe_address,
                self.safe_balance,
            ]
        )
