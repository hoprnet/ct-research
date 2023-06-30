class Settings:
    """
    Settings for running the Sanic app.
    """
    DEV: bool = True
    HOST: str = "localhost"
    PORT: int = 8080
    FAST: bool = False