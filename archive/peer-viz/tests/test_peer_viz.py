import pytest
import os
from peer_viz import _getenvvar 

# Load Dummy environment variables
os.environ["HOPR_NODE_1"] = "api_host"
os.environ["HOPR_NODE_1_API_KEY"] = "api_key"

# test that environment variables are loaded correctly 
def test_getenvvar() -> None:
    envvar_0 = _getenvvar("HOPR_NODE_1")
    envvar_1 = _getenvvar("HOPR_NODE_1_API_KEY")
    assert envvar_0 == "api_host"
    assert envvar_1 == "api_key" 

# test whether the system exit works 
def test_getenvvar_exit() -> None:
    
    # Remove the environment variable 
    os.environ.pop("HOPR_NODE_1")
    
    # call function and capture output
    with pytest.raises(SystemExit) as exc_info:
        _getenvvar("HOPR_NODE_1")
    
    # assert that sys.exit was called with code 1 and error message was printed
    assert exc_info.type == SystemExit
    assert exc_info.value.code == 1
    

