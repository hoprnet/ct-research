from .query_provider import BalanceProvider, DistributorProvider


class HOPRBalance(BalanceProvider):
    token_contract: str = "0xF5581dFeFD8Fb0e4aeC526bE659CFaB1f8c781dA"
    symbol: str = "wxHOPR"


class xHOPRBalance(BalanceProvider):
    token_contract: str = "0xD057604A14982FE8D88c5fC25Aac3267eA142a08"
    symbol: str = "wxHOPR"


class wxHOPRBalance(BalanceProvider):
    token_contract: str = "0xD4fdec44DB9D44B8f2b6d529620f9C0C7066A2c1"
    symbol: str = "wxHOPR"


class GnosisDistributor(DistributorProvider):
    contract: str = "0x987cb736fBfBc4a397Acd06045bf0cD9B9deFe66"
    symbol: str = "wxHOPR"


class MainnetDistributor(DistributorProvider):
    contract: str = "0xB413a589ec21Cc1FEc27d1175105a47628676552"
    symbol: str = "wxHOPR"
