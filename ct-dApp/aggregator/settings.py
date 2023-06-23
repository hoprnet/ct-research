from sanic_envconfig import EnvConfig


class Settings(EnvConfig):
    """
    Settings for running the Sanic app.
    """
    DEV: bool = True
    HOST: str = "localhost"
    PORT: int = 8080
    FAST: bool = False