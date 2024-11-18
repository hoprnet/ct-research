class ApiRequestObject:
    def __init__(self, *args, **kwargs):
        kwargs.update(args[0])

        kwargs.pop("self", None)

        # pop all field starting with __ from kwargs
        for key in list(kwargs.keys()):
            if key.startswith("__"):
                kwargs.pop(key)

        if set(kwargs.keys()) != set(self.keys.keys()):
            raise ValueError(
                f"Keys mismatch: {set(kwargs.keys())} != {set(self.keys.keys())}"
            )

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
        print(f"{vars()=}")
        super().__init__(vars())


class CreateSessionBody(ApiRequestObject):
    keys = {
        "capabilities": "capabilities",
        "destination": "destination",
        "listen_host": "listenHost",
        "path": "path",
        "target": "target",
    }

    def __init__(
        self,
        capabilities: list,
        destination: str,
        listen_host: str,
        path: str,
        target: str,
    ):
        super().__init__(vars())


class SessionCapabilitiesBody(ApiRequestObject):
    keys = {
        "retransmission": "Retransmission",
        "segmentation": "Segmentation",
    }

    def __init__(self, retransmission: bool, segmentation: bool):
        super().__init__(vars())

    @property
    def as_array(self) -> list:
        return [self.keys[var] for var in vars(self) if vars(self)[var]]


class SessionPathBody(ApiRequestObject):
    keys = {
        "relayer": "relayer",
    }

    def __init__(self, relayer: str):
        super().__init__(vars())


class SessionTargetBody(ApiRequestObject):
    keys = {
        "plain_target": "Plain",
    }

    def __init__(self, plain_target: str):
        super().__init__(vars())


class DeleteSessionBody(ApiRequestObject):
    keys = {"ip": "listeningIp", "port": "port"}

    def __init__(self, ip: str, port: str):
        super().__init__(vars())
