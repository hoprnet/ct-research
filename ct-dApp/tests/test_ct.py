import pytest
import os
from ct import _getenvvar 

def test_getenvvar_load_envar() -> None:
    """
    Test whether the global evironment variables are loaded correctly.
    """
    os.environ['HOPR_NODE_1_HTTP_URL'] = 'http_url'
    os.environ['HOPR_NODE_1_API_KEY'] = 'api_key'

    envvar_0 = _getenvvar('HOPR_NODE_1_HTTP_URL')
    envvar_1 = _getenvvar('HOPR_NODE_1_API_KEY')
    assert envvar_0 == 'http_url'
    assert envvar_1 == 'api_key' 

def test_getenvvar_exit() -> None:
    """
    Test whether system exit is called when no environemnt variable is provided.
    """
    os.environ.pop('HOPR_NODE_1_HTTP_URL')
    
    with pytest.raises(SystemExit) as exc_info:
        _getenvvar('HOPR_NODE_1_HTTP_URL')
    
    assert exc_info.type == SystemExit
    assert exc_info.value.code == 1
 