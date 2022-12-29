# =============================================================================
# Access HOPR Node and Compute Latency and Network Bandwidth 
# =============================================================================

import json
import logging
import os 
import random
import requests
import sys
from datetime import datetime

# set logging level
logging.basicConfig(filename='peer_viz.log',
                    level=logging.DEBUG,
                    format='%(levelname)s:%(asctime)s:%(message)s')

## set debugging mode for all websocket connection
#websocket.enableTrace(True)

def _getenvvar(name: str) -> str:
    """
    Returns the string contained in environment variable `name` or None.
    """
    ret_value = None
    if os.getenv(name) is None:
        print("Environment variable", name, "not found")
        sys.exit(1)
    else:
        ret_value = os.getenv(name)
    return ret_value


if __name__ == "__main__":
    # read parameters from environment variables
    api_host = _getenvvar('HOPR_NODE_1')
    api_key  = _getenvvar('HOPR_NODE_1_API_KEY')

    # get address id of api host and verify that the api host is still available
    address_url = "https://{}:3001/api/v2/account/addresses".format(api_host)
    print(address_url)
    headers     = {
      'X-Auth-Token': api_key
    }
    address_response = requests.request("GET",
                                        address_url,
                                        headers=headers)
    my_pid = None
    if (address_response.status_code == 200): # 200: Address fetched successfully
        my_pid = address_response.json()['hoprAddress']
        logging.info("Host available (PID {})".format(my_pid))
    else:
        logging.error("Host is NOT available: start a new cluster. Status code: {}".format(address_response.status_code))
        sys.exit(1)
        
    # get information about the api host's peers
    peer_url = "https://{}:3001/api/v2/node/peers?quality=0.5".format(api_host)
    headers     = {
      'X-Auth-Token': api_key
    }
    peer_response = requests.request("GET",
                                     peer_url,
                                     headers=headers)
    
    if (peer_response.status_code != 200):
        logging.error("Could not fetch peer information. Status code: {}".format(peer_response.status_code))
        sys.exit(1)

    # double check that the number of connected peers is not greater than the announced ones
    connected_peers = peer_response.json()['connected']
    print(connected_peers)
    announced_peers = peer_response.json()['announced']
    assert(len(connected_peers) <= len(announced_peers))

    # create list of peer id's
    api_host_peers = []
    for i in range(len(connected_peers)):
        peer = json.dumps(peer_response.json()['connected'][i]['peerId'], indent=4)
        api_host_peers.append(peer.strip('"'))

    # my PID should never appear as one of my peers
    assert(my_pid not in api_host_peers)
    
    print(api_host_peers)
    
    # Get payment channel Information 
    channel_url = "https://{}:3001/api/v2/channels/".format(api_host)
    headers     = {
      'X-Auth-Token': api_key
    }
    channel_response = requests.request("GET",
                                channel_url,
                                headers=headers)
    print(">>> Channel information <<<")
    print(channel_response.status_code)
    print(json.dumps(channel_response.json(), indent=4))
    
    sys.exit(1)
    