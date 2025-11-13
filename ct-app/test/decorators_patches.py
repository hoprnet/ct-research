from unittest.mock import patch

patches = [
    patch("core.components.decorators.keepalive", lambda x: x),
    patch("core.components.decorators.connectguard", lambda x: x),
]

for p in patches:
    p.start()
