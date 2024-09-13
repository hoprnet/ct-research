from core.components.parameters import Parameters

from .subgraph_type import SubgraphType


class SubgraphURL:
    def __init__(self, params: Parameters, key):
        super().__init__()
        self.params = getattr(params, key)
        self.deployer_key = params.apiKey
        self.user_id = params.userID
        self.type = SubgraphType.DEFAULT

        self._urls = {
            SubgraphType.DEFAULT: self._construct_default(),
            SubgraphType.BACKUP: self._construct_backup(),
            SubgraphType.NONE: None,
        }

    def _construct_default(self):
        return f"https://gateway-arbitrum.network.thegraph.com/api/{self.deployer_key}/subgraphs/id/{self.params.queryID}"

    def _construct_backup(self):
        return f"https://api.studio.thegraph.com/query/{self.user_id}/{self.params.slug}/{getattr(self.params, 'version','version/latest')}"

    def __getitem__(self, index: SubgraphType) -> str:
        return self._urls.get(index, None)

    @property
    def url(self) -> str:
        return self[self.type]
