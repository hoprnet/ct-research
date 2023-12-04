class TableEntry:
    def __init__(self):
        self._peer_id = None
        self._node_address = None
        self._channels_balance = None
        self._safe_address = None
        self._safe_balance = None
        self._total_balance = None
        self._safe_address_count = None
        self._split_stake = None
        self._transformed_stake = None
        self._apr_percentage = None
        self._expected_reward = None
        self._airdrop_reward = None
        self._protocol_reward = None
        self._protocol_reward_per_distribution = None
        self._message_count_for_reward = None

    @property
    def peer_id(self):
        return self._peer_id

    @peer_id.setter
    def peer_id(self, value):
        self._peer_id = value

    @property
    def node_address(self):
        return self._node_address

    @node_address.setter
    def node_address(self, value):
        self._node_address = value

    @property
    def channels_balance(self):
        return float(self._channels_balance)

    @channels_balance.setter
    def channels_balance(self, value):
        self._channels_balance = value

    @property
    def node_peer_ids(self):
        return self._node_peer_ids

    @node_peer_ids.setter
    def node_peer_ids(self, value):
        self._node_peer_ids = value

    @property
    def safe_address(self):
        return self._safe_address

    @safe_address.setter
    def safe_address(self, value):
        self._safe_address = value

    @property
    def safe_balance(self):
        return float(self._safe_balance)

    @safe_balance.setter
    def safe_balance(self, value):
        self._safe_balance = value

    @property
    def total_balance(self):
        return float(self._total_balance)

    @total_balance.setter
    def total_balance(self, value):
        self._total_balance = value

    @property
    def safe_address_count(self):
        return float(self._safe_address_count)

    @safe_address_count.setter
    def safe_address_count(self, value):
        self._safe_address_count = value

    @property
    def split_stake(self):
        return float(self._split_stake)

    @split_stake.setter
    def split_stake(self, value):
        self._split_stake = value

    @property
    def transformed_stake(self):
        return float(self._transformed_stake)

    @transformed_stake.setter
    def transformed_stake(self, value):
        self._transformed_stake = value

    @property
    def prob(self):
        return float(self._prob)

    @prob.setter
    def prob(self, value):
        self._prob = value

    @property
    def budget(self):
        return float(self._budget)

    @budget.setter
    def budget(self, value):
        self._budget = value

    @property
    def budget_split_ratio(self):
        return float(self._budget_split_ratio)

    @budget_split_ratio.setter
    def budget_split_ratio(self, value):
        self._budget_split_ratio = value

    @property
    def distribution_frequency(self):
        if self._distribution_frequency is None:
            return None
        return float(self._distribution_frequency)

    @distribution_frequency.setter
    def distribution_frequency(self, value):
        self._distribution_frequency = value

    @property
    def budget_period_in_sec(self):
        return float(self._budget_period_in_sec)

    @budget_period_in_sec.setter
    def budget_period_in_sec(self, value):
        self._budget_period_in_sec = value

    @property
    def apr_percentage(self):
        return float(self._apr_percentage)

    @apr_percentage.setter
    def apr_percentage(self, value):
        self._apr_percentage = value

    @property
    def expected_reward(self):
        if self._expected_reward is None:
            return 0
        return float(self._expected_reward)

    @expected_reward.setter
    def expected_reward(self, value):
        self._expected_reward = value

    @property
    def airdrop_reward(self):
        return float(self._airdrop_reward)

    @airdrop_reward.setter
    def airdrop_reward(self, value):
        self._airdrop_reward = value

    @property
    def protocol_reward(self):
        return float(self._protocol_reward)

    @protocol_reward.setter
    def protocol_reward(self, value):
        self._protocol_reward = value

    @property
    def protocol_reward_per_distribution(self):
        return float(self._protocol_reward_per_distribution)

    @protocol_reward_per_distribution.setter
    def protocol_reward_per_distribution(self, value):
        self._protocol_reward_per_distribution = value

    @property
    def ticket_price(self):
        return float(self._ticket_price)

    @ticket_price.setter
    def ticket_price(self, value):
        self._ticket_price = value

    @property
    def winning_prob(self):
        return float(self._winning_prob)

    @winning_prob.setter
    def winning_prob(self, value):
        self._winning_prob = value

    @property
    def message_count_for_reward(self):
        return float(self._message_count_for_reward)

    @message_count_for_reward.setter
    def message_count_for_reward(self, value):
        self._message_count_for_reward = value

    @classmethod
    def fromList(cls, headers, item):
        entry = cls()

        for header, value in zip(headers, item):
            setattr(entry, header, value)

        return entry

    def __repr__(self):
        return (
            f"TableEntry(peer_id: {self.peer_id}, "
            + f"address: {self.source_node_address}, "
            + f"rewards/dist: {self.reward_per_dist})"
        )
