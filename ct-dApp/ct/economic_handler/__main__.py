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

    economic_handler = EconomicHandler(API_host, API_key)
    #result = await economic_handler.channel_topology()
    #result_1 = economic_handler.replace_keys_in_mock_data(result)
    #result_2 = economic_handler.replace_keys_in_mock_data_subgraph(result)

    #print(result_1)
    #print(result_2)
    parameters, equations = economic_handler.read_parameters_and_equations()
    print(parameters)
    print(equations)

    result = economic_handler.blacklist_rpch_nodes(api_endpoint=RPCH_nodes)
    print(result)

if __name__ == "__main__":
    asyncio.run(main())

