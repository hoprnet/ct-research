from .base_classes import ExplicitParams


class SubgraphEndpointParams(ExplicitParams):
    keys = {"query_id": str, "slug": str, "inputs": dict}


class SubgraphParams(ExplicitParams):
    keys = {
        "type": str,
        "user_id": int,
        "api_key": str,
        "mainnet_allocations": SubgraphEndpointParams,
        "gnosis_allocations": SubgraphEndpointParams,
        "hopr_on_mainnet": SubgraphEndpointParams,
        "hopr_on_gnosis": SubgraphEndpointParams,
        "safes_balance": SubgraphEndpointParams,
        "fundings": SubgraphEndpointParams,
        "rewards": SubgraphEndpointParams,
        "staking": SubgraphEndpointParams,
    }
