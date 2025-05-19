class ApiRequestObject:
    def __init__(self, *args, **kwargs):
        if not hasattr(self, "keys"):
            self.keys = {}

        if args:
            kwargs.update(args[0])

        kwargs = {k: v for k, v in kwargs.items() if not k.startswith("__")}
        kwargs.pop("self", None)

        if set(kwargs.keys()) != set(self.keys.keys()):
            raise ValueError(f"Keys mismatch: {set(kwargs.keys())} != {set(self.keys.keys())}")

        for key, value in kwargs.items():
            setattr(self, key, value)

        self.post_init()

    @property
    def as_dict(self) -> dict:
        return {value: getattr(self, key) for key, value in self.keys.items()}

    @property
    def as_header_string(self) -> str:
        attrs_as_dict = {value: getattr(self, key) for key, value in self.keys.items()}
        return "&".join([f"{k}={v}" for k, v in attrs_as_dict.items()])

    def post_init(self):
        pass


class OpenChannelBody(ApiRequestObject):
    keys = {
        "amount": "amount",
        "peer_address": "peerAddress",
    }

    def __init__(self, amount: str, peer_address: str):
        super().__init__(vars())


class FundChannelBody(ApiRequestObject):
    keys = {"amount": "amount"}

    def __init__(self, amount: float):
        super().__init__(vars())

    def post_init(self):
        self.amount = f"{self.amount:.0f}"


class GetChannelsBody(ApiRequestObject):
    keys = {
        "full_topology": "fullTopology",
        "including_closed": "includingClosed",
    }

    def __init__(self, full_topology: str, including_closed: str):
        super().__init__(vars())


class GetPeersBody(ApiRequestObject):
    keys = {"quality": "quality"}

    def __init__(self, quality: float):
        super().__init__(vars())


class CreateSessionBody(ApiRequestObject):
    keys = {
        "capabilities": "capabilities",
        "destination": "destination",
        "listen_host": "listenHost",
        "forward_path": "forwardPath",
        "return_path": "returnPath",
        "response_buffer": "responseBuffer",
        "target": "target",
    }

    def __init__(
        self,
        capabilities: list,
        destination: str,
        listen_host: str,
        forward_path: str | dict,
        return_path: str | dict,
        response_buffer: str,
        target: str | dict,
    ):
        super().__init__(vars())


class SessionCapabilitiesBody(ApiRequestObject):
    keys = {
        "retransmission": "Retransmission",
        "segmentation": "Segmentation",
        "no_delay": "NoDelay",
    }

    def __init__(self, retransmission: bool, segmentation: bool, no_delay: bool):
        super().__init__(vars())

    @property
    def as_array(self) -> list:
        return [self.keys[var] for var in vars(self) if var in self.keys and vars(self)[var]]


class SessionPathBodyRelayers(ApiRequestObject):
    keys = {
        "relayers": "IntermediatePath",
    }

    def __init__(self, relayers: list[str]):
        super().__init__(vars())


class SessionPathBodyHops(ApiRequestObject):
    keys = {
        "hops": "Hops",
    }

    def __init__(self, hops: int = 0):
        super().__init__(vars())

    def post_init(self):
        self.hops = int(self.hops)


class SessionTargetBody(ApiRequestObject):
    keys = {
        "service": "Service",
    }

    def __init__(self, service: int = 0):
        super().__init__(vars())
