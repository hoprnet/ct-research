from web3 import Web3

import logging

logging.basicConfig()
logging.getLogger("asyncio").setLevel(logging.WARNING)
formatter = logging.Formatter("%(asctime)s %(levelname)s:%(message)s")


class SubgraphEntry:
    _web3 = None  # Class variable to store Web3 instance
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    logger = logging.getLogger("ct-app:subgraph")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    def __str__(self):
        cls = self.__class__.__name__
        fields = ", ".join(f"{field}={value}" for field, value in vars(self).items())

        return f"{cls}({fields})"

    def __repr__(self):
        return str(self)

    def __eq__(self, other):
        return vars(self) == vars(other)

    @classmethod
    def checksum(cls, address: str):
        if not cls._web3:
            cls._web3 = Web3()
    
        cls.logger.info(f"subgraph: Checksumming address {address}")
        try:
            checksummed = cls._web3.to_checksum_address(address)
            cls.logger.info(f"subgraph: Checksummed address {address} => {checksummed}")
            return checksummed
        except ValueError:
            pass
        except TypeError:
            pass

        cls.logger.error(f"subgraph: Not using a checksummed address due to failure, using {address}")
        return address
