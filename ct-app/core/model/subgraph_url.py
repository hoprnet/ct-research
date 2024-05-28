from .subgraph_type import SubgraphType


class SubgraphURL:
    def __init__(self, default: str, backup: str):
        super().__init__()

        self._urls = {
            SubgraphType.DEFAULT: default,
            SubgraphType.BACKUP: backup,
            SubgraphType.NONE: None,
        }

    def __call__(self, type: SubgraphType) -> str:
        return self._urls[type]
