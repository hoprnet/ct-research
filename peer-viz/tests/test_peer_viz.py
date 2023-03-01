from peer_viz import _getenvvar 
import os

# Load Dummy environment variable 
os.environ["HOPR_NODE_1"] = "ip_address"

def test_getenvvar() -> None:
    envvar = _getenvvar("HOPR_NODE_1") 
    assert envvar == "ip_address"