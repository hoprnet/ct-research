from unittest.mock import patch


def _mock_decorator(f):
    def decorated_function(g):
        return g

    if callable(f):
        return decorated_function(f)
    return decorated_function


patches = [
    patch("core.components.decorators.formalin", _mock_decorator),
    patch("core.components.decorators.flagguard", _mock_decorator),
]

for p in patches:
    p.start()
