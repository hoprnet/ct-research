from peer_viz import _getenvvar 
import os

# Load Dummy environment variable 
os.environ["HOPR_NODE_1"] = "ip_address"
os.environ["HOPR_NODE_1_API_KEY"] = "api_key"

def test_getenvvar() -> None:
    envvar_0 = _getenvvar("HOPR_NODE_1")
    envvar_1 = _getenvvar("HOPR_NODE_1_API_KEY")
    assert envvar_0 == "ip_address"
    assert envvar_1 == "api_key" 

