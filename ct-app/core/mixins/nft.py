import logging

from prometheus_client import Gauge

from ..components.logs import configure_logging
from .protocols import HasNFT, HasParams

NFT_HOLDERS = Gauge("ct_nft_holders", "Number of nr-nft holders")


configure_logging()
logger = logging.getLogger(__name__)


class NftMixin(HasNFT, HasParams):
    def get_nft_holders(self):
        """
        Gets all NFT holders.
        """
        with open(self.params.nft_holders.filepath, "r") as f:
            data: list[str] = [line.strip() for line in f if line.strip()]

        if len(data) == 0:
            logger.warning("No NFT holders data found")

        self.nft_holders_data: list[str] = data

        logger.debug("Fetched NFT holders", {"count": len(self.nft_holders_data)})
        NFT_HOLDERS.set(len(self.nft_holders_data))
