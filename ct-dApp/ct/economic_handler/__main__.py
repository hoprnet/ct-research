import asyncio
from ..exit_codes import ExitCode
from ..utils import _getenvvar
from .economic_handler import EconomicHandler

async def main():
    """main"""
    try:
        API_host = _getenvvar("HOPR_NODE_1_HTTP_URL")
        API_key = _getenvvar("HOPR_NODE_1_API_KEY")
        RPCH_nodes = _getenvvar("RPCH_NODES_API_ENDPOINT")
    except ValueError:
        exit(ExitCode.ERROR_BAD_ARGUMENTS)

    print(API_host)
    print(API_key)
    print(RPCH_nodes)

    economic_handler = EconomicHandler(API_host, API_key)

    tasks = [
        economic_handler.channel_topology(),
        economic_handler.read_parameters_and_equations(),
        economic_handler.blacklist_rpch_nodes(api_endpoint=RPCH_nodes)
    ]

    result = await asyncio.gather(*tasks)
    channel_topology_result, parameters_equations_budget_result, blacklist_result = result

    print(channel_topology_result)
    print(parameters_equations_budget_result[0])  # parameters
    print(parameters_equations_budget_result[1])  # equations
    print(parameters_equations_budget_result[2])  # budget
    print(blacklist_result) # RPCh nodes blacklist

    # helper functions that allow to test the code (subject to removal)
    result_1 = economic_handler.replace_keys_in_mock_data(channel_topology_result)
    result_2 = economic_handler.replace_keys_in_mock_data_subgraph(channel_topology_result)

    # merge channel topology with metrics from the database and subgraph data
    result_3 = economic_handler.merge_topology_metricdb_subgraph(channel_topology_result,
                                                                result_1, result_2
                                                                )

    # computation of cover traffic probability
    result_4 = economic_handler.compute_ct_prob(parameters_equations_budget_result[0],
                                                parameters_equations_budget_result[1],
                                                result_3)

    # calculate expected rewards and output it as a csv file
    result_5 = economic_handler.compute_expected_reward_savecsv(result_4,
                                                                parameters_equations_budget_result[2]
                                                                )

    print(blacklist_result) # RPCh nodes blacklist (not yet included: would need to mock it)
    print(result_5)

if __name__ == "__main__":
    asyncio.run(main())

