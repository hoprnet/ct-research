from web3 import Web3


class SubgraphEntry:
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
        try:
            return Web3().to_checksum_address(address)
        except ValueError:
            pass
        except TypeError:
            pass
        return address
