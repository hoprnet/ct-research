from core.components.parameters import Parameters

from .mode import Mode


class URL:
    def __init__(self, params: Parameters, key: str):
        """
        Initializes a URL instance with parameters and precomputes URLs for each mode.
        
        Extracts relevant parameter subsets and identifiers, sets the default mode, and prepares URL strings for all supported operational modes.
        """
        super().__init__()
        self.params = getattr(params, key)
        self.deployer_key = params.apiKey
        self.user_id = params.userID
        self.mode = Mode.DEFAULT

        self._urls = {
            Mode.DEFAULT: self._construct_default(),
            Mode.BACKUP: self._construct_backup(),
            Mode.NONE: None,
        }

    def _construct_default(self):
        """
        Constructs the default mode URL using the deployer API key and query ID.
        
        Returns:
            The formatted URL string for the default operational mode.
        """
        base = "https://gateway-arbitrum.network.thegraph.com/api/%s/subgraphs/id/%s"
        return base % (self.deployer_key, self.params.queryID)

    def _construct_backup(self):
        """
        Constructs the backup mode URL using the user ID, slug, and version.
        
        If the version parameter is not present, defaults to "version/latest".
        Returns:
            The constructed backup URL as a string.
        """
        base = "https://api.studio.thegraph.com/query/%s/%s/%s"
        version = getattr(self.params, "version", "version/latest")
        return base % (self.user_id, self.params.slug, version)

    def __getitem__(self, index: Mode) -> str:
        """
        Returns the URL string associated with the specified mode, or None if not available.
        
        Args:
            index: The mode for which to retrieve the URL.
        
        Returns:
            The URL string for the given mode, or None if the mode is not present.
        """
        return self._urls.get(index, None)

    @property
    def url(self) -> str:
        return self[self.mode]
