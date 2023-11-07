class TableEntry:
    def __init__(self):
        self._peer_id = None
        self._source_node_address = None
        self._channels_balance = None
        self._node_peer_ids = None
        self._safe_address = None
        self._safe_balance = None
        self._total_balance = None
        self._safe_address_count = None
        self._splitted_stake = None
        self._trans_stake = None
        self._prob = None
        self._budget = None
        self._budget_split_ratio = None
        self._distribution_frequency = None
        self._budget_period_in_sec = None
        self._apy_pct = None
        self._total_expected_reward = None
        self._airdrop_expected_reward = None
        self._protocol_exp_reward = None
        self._protocol_exp_reward_per_dist = None
        self._ticket_price = None
        self._winning_prob = None
        self._jobs = None

    @property
    def peer_id(self):
        return self._peer_id

    @peer_id.setter
    def peer_id(self, value):
        self._peer_id = value

    @property
    def source_node_address(self):
        return self._source_node_address

    @source_node_address.setter
    def source_node_address(self, value):
        self._source_node_address = value

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
    def splitted_stake(self):
        return float(self._splitted_stake)

    @splitted_stake.setter
    def splitted_stake(self, value):
        self._splitted_stake = value

    @property
    def trans_stake(self):
        return float(self._trans_stake)

    @trans_stake.setter
    def trans_stake(self, value):
        self._trans_stake = value

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
    def apy_pct(self):
        return float(self._apy_pct)

    @apy_pct.setter
    def apy_pct(self, value):
        self._apy_pct = value

    @property
    def total_expected_reward(self):
        return float(self._total_expected_reward)

    @total_expected_reward.setter
    def total_expected_reward(self, value):
        self._total_expected_reward = value

    @property
    def airdrop_expected_reward(self):
        return float(self._airdrop_expected_reward)

    @airdrop_expected_reward.setter
    def airdrop_expected_reward(self, value):
        self._airdrop_expected_reward = value

    @property
    def protocol_exp_reward(self):
        return float(self._protocol_exp_reward)

    @protocol_exp_reward.setter
    def protocol_exp_reward(self, value):
        self._protocol_exp_reward = value

    @property
    def protocol_exp_reward_per_dist(self):
        return float(self._protocol_exp_reward_per_dist)

    @protocol_exp_reward_per_dist.setter
    def protocol_exp_reward_per_dist(self, value):
        self._protocol_exp_reward_per_dist = value

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
    def jobs(self):
        return float(self._jobs)

    @jobs.setter
    def jobs(self, value):
        self._jobs = value

    @property
    def reward_per_dist(self):
        return self.total_expected_reward / self.distribution_frequency

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
