from sanic_envconfig import EnvConfig


class Settings(EnvConfig):
    DEV: bool = True
    HOST: str = "localhost"
    PORT: int = 8080
    FAST: bool = False