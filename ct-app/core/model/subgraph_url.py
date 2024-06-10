from core.components.parameters import Parameters

from .subgraph_type import SubgraphType


class SubgraphURL:
    def __init__(self, deployer_key: str, param_set: Parameters):
        super().__init__()
        self.param_set = param_set
        self.deployer_key = deployer_key

        self._urls = {
            SubgraphType.DEFAULT: self._construct_default(),
            SubgraphType.BACKUP: self._construct_backup(),
            SubgraphType.NONE: None,
        }

    def _construct_default(self):
        if not self.param_set.queryID:
            return self._construct_backup()

        return f"https://gateway.thegraph.com/api/{self.deployer_key}/subgraphs/id/{self.param_set.queryID}"

    def _construct_backup(self):
        return self.param_set.URLBackup

    def __call__(self, type: SubgraphType) -> str:
        return self._urls.get(type, None)
