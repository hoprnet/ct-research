from .graphql_provider import GraphQLProvider


class Safes(GraphQLProvider):
    query_file = "queries/safes_balance.graphql"


class Rewards(GraphQLProvider):
    query_file = "queries/rewards.graphql"
