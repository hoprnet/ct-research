from .utils import Utils


class Parameters:
    def __init__(self):
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

    def __call__(self, env_prefix: str):
        for key, value in Utils.envvarWithPrefix(env_prefix).items():
            k = key.replace(env_prefix, "").lower()

            try:
                value = float(value)
            except ValueError:
                pass

            try:
                integer = int(value)
                if integer == value:
                    value = integer

            except ValueError:
                pass

            setattr(self, k, value)

        return self

    def __str__(self):
        return
