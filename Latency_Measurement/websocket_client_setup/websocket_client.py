# =============================================================================
# Access HOPR Node and Compute Latency and Network Bandwidth 
# =============================================================================

import json
import logging
import os 
import random
import requests
import ssl
import sys
import websocket
from datetime import datetime

# set logging level
logging.basicConfig(filename='websocket_client.log',
                    level=logging.INFO,
                    format='%(levelname)s:%(asctime)s:%(message)s')

# set debugging mode for all websocket connection
websocket.enableTrace(True)



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
    api_host = _getenvvar('HOPR_API_HOST')
    api_key  = _getenvvar('HOPR_API_KEY')

    # get address id of api host and verify that the api host is still available
    address_url = "https://{}:3001/api/v2/account/addresses".format(api_host)
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
    peer_url = "https://{}:3001/api/v2/node/peers".format(api_host)
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
    announced_peers = peer_response.json()['announced']
    assert(len(connected_peers) <= len(announced_peers))

    # create list of peer id's
    api_host_peers = []
    for i in range(len(connected_peers)):
        peer = json.dumps(peer_response.json()['connected'][i]['peerId'], indent=4)
        api_host_peers.append(peer.strip('"'))

    # my PID should never appear as one of my peers
    assert(my_pid not in api_host_peers)

    # send a meesage to ourselves through a random peer
    path     = [random.choice(api_host_peers)]
    send_url = "https://{}:3001/api/v2/messages/".format(api_host)
    headers  = {
      'X-Auth-Token': api_key,
      'Content-Type': 'application/json'
    }
    logging.info("Sending message to self through: {}".format(path))

    payload = json.dumps({
      "body": str(datetime.now()), # send current time stamp as message content 
      "recipient": my_pid,
      "path": path
    })

    send_response = requests.request("POST",
                                     send_url,
                                     headers=headers,
                                     data=payload)
    
    if (send_response.status_code != 202): # 202: message sent successfully
        logging.error("Could not send message. Status code: {}".format(send_response.status_code))
        sys.exit(1)
    
    sys.exit(1)
    
    #print(str(datetime.now()))
    
    # Get payment channel Information 
    # =========================================================================
    
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
    
    # =============================================================================
    # Stream incomming messages for a node     
    # =============================================================================
    # An example from Kraken documentation:
    #
    #    # Connect to WebSocket API and subscribe to trade feed for XBT/USD and XRP/USD
    #    ws = create_connection("wss://ws.kraken.com/")
    #    ws.send('{"event":"subscribe", "subscription":{"name":"trade"}, "pair":["XBT/USD","XRP/USD"]}')
    #
    #    # Infinite loop waiting for WebSocket data
    #    while True:
    #        print(ws.recv())
    #

    # Set-up websocket client   
    # ws = websocket.WebSocket(sslopt={"cert_reqs": ssl.CERT_NONE})
    # ws.connect("wss://zero_mekong_silver_phobos.playground.hoprnet.org:3001/api/v2/messages/websocket?apiToken=adb01Cd949aC1b24c7CC4Da8%23")
    # record  = ws.recv()
    # print(record)

else: sys.exit(1)
