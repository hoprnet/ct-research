class Parameters:
    def __init__(self):
        self.channel_min_balance = 1
        self.channel_funding_amount = 10

        self.subgraph_query = """
            query SafeNodeBalance($first: Int, $skip: Int) {
                safes(first: $first, skip: $skip) {
                    registeredNodesInNetworkRegistry {
                        node { id }
                        safe { id balance { wxHoprBalance } }
                    }
                }
            }
        """
        self.subgraph_pagination_size = 1000

        self.economic_model_filename = "parameters-production.json"
        self.min_eligible_peers = 5

    def __str__(self):
        return
