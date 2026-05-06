from .blokli_provider import BlokliProvider
from .entries import (
    BlokliAccount,
    BlokliHoprBalance,
    BlokliRedemptionStats,
)


class HoprBalance(BlokliProvider[BlokliHoprBalance]):
    query_file: str = "queries/balance.graphql"
    params = ["$address: String!"]


class AccountSubscription(BlokliProvider[BlokliAccount]):
    query_file: str = "queries/accounts.graphql"


class Redemptions(BlokliProvider[BlokliRedemptionStats]):
    query_file: str = "queries/redemptions.graphql"
    params = ["$safe_address: String", "$node_address: String"]
