from core.components.parameters import Parameters

from .subgraph_type import SubgraphType


class SubgraphURL:

    def __init__(self, params: Parameters, key: str):
        super().__init__()
        self.params = getattr(params, key)
        self.deployer_key = params.apiKey
        self.user_id = params.userID

        self._urls = {
            SubgraphType.DEFAULT: self._construct_default(),
            SubgraphType.BACKUP: self._construct_backup(),
            SubgraphType.NONE: None,
        }

    def _construct_default(self):
        if not self.params.queryID:
            return self._construct_backup()

        return f"https://gateway-arbitrum.network.thegraph.com/api/{self.deployer_key}/subgraphs/id/{self.params.queryID}"

    def _construct_backup(self):
        return f"https://api.studio.thegraph.com/query/{self.user_id}/{self.params.slug}/{self.params.version}"

    def __getitem__(self, index: SubgraphType) -> str:
        return self._urls.get(index, None)
