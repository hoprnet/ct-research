from .graphql_provider import GraphQLProvider


class Safes(GraphQLProvider):
    query_file = "queries/safes_balance.graphql"


class Staking(GraphQLProvider):
    query_file = "queries/staking.graphql"


class Rewards(GraphQLProvider):
    query_file = "queries/rewards.graphql"


class Allocations(GraphQLProvider):
    query_file = "queries/allocations.graphql"
    params = ['$schedule_in: [String!] = [""]']


class Fundings(GraphQLProvider):
    query_file = "queries/fundings.graphql"
    params = ['$from: String = ""', '$to_in: [String!] = [""]']


class EOABalance(GraphQLProvider):
    query_file = "queries/eoa_balance.graphql"
    params = ['$id_in: [Bytes!] = [""]']
