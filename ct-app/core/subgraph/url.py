from typing import Optional

from ..components.config_parser import SubgraphEndpointParams
from .mode import Mode


class URL:
    def __init__(self, user_id: str, api_key: str, params: SubgraphEndpointParams):
        super().__init__()
        self.params = params
        self.deployer_key = api_key
        self.user_id = user_id
        self.mode = Mode.DEFAULT

        self._urls = {
            Mode.DEFAULT: self._construct_default(),
            Mode.BACKUP: self._construct_backup(),
            Mode.NONE: None,
        }

    def _construct_default(self) -> str:
        base = "https://gateway-arbitrum.network.thegraph.com/api/%s/subgraphs/id/%s"
        return base % (self.deployer_key, self.params.query_id)

    def _construct_backup(self) -> str:
        base = "https://api.studio.thegraph.com/query/%s/%s/%s"
        version = getattr(self.params, "version", "version/latest")
        return base % (self.user_id, self.params.slug, version)

    def __getitem__(self, index: Mode) -> Optional[str]:
        return self._urls.get(index, None)

    @property
    def url(self) -> Optional[str]:
        return self[self.mode]
