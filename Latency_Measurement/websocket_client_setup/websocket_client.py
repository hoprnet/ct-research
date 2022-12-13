# =============================================================================
# Access HOPR Node and Compute Latency and Network Bandwidth 
# =============================================================================

import json
import os 
import requests
import ssl
import sys
import websocket
from datetime import datetime

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

    # Get address id of api host and verify that the api host is still available
    # =========================================================================
    
    address_url = "https://{}:3001/api/v2/account/addresses".format(api_host)
    headers     = {
      'X-Auth-Token': api_key
    }
    address_response = requests.request("GET",
                                address_url,
                                headers=headers)
     
    if (address_response.status_code == 200): # 200: Address fetched successfully 
        print("API host is available, ",
              "Status code:", address_response.status_code,
              ", address:", json.dumps(address_response.json()['hoprAddress'], indent=4))
    else:
        print("API host is NOT available: start a new cluster, ",
              "Status code:", address_response.status_code)
        sys.exit(1)   
        
    # Get information about the api host's peers 
    # =========================================================================
    
    peer_url = "https://{}:3001/api/v2/node/peers".format(api_host)
    headers     = {
      'X-Auth-Token': api_key
    }
    peer_response = requests.request("GET",
                                peer_url,
                                headers=headers)
    
    if (peer_response.status_code == 200): # 200: Peer information fetched successfully 
        print("Peer information fetched successfully, ",
              "Status code:", peer_response.status_code)       
    else:
        print("Could not fetch peer information, ", 
              "Status code:", peer_response.status_code)
        sys.exit(1)   
    
    # Create list of peer id's
    api_host_peers = []
    for i in range(4):
        peer = json.dumps(peer_response.json()['connected'][i]['peerId'], indent=4)
        api_host_peers.append(peer.strip('\"')) # strip: Remove double quotes from string
    
    print("Peers:", api_host_peers)
    
    # Define message path 
    # =========================================================================
    
    # Select between 1 HOP, 2 HOP, or 3 HOP message 
    path = [api_host_peers[0]]                                       # 1 HOP Message
    #path = [api_host_peers[0], api_host_peers[1]]                    # 2 HOP Message
    #path = [api_host_peers[0], api_host_peers[1], api_host_peers[2]] # 3 HOP Message
    
    # Send a meesage to a peer  
    # =========================================================================
    
    send_url  = "https://{}:3001/api/v2/messages/".format(api_host)
    recv_peer = address_response.json()['hoprAddress'] # sets api host as recipient 
    #recv_peer = api_host_peers[1] # set other peer as the recipient 
    print("Message Recipient:", recv_peer)

    headers = {
      'X-Auth-Token': api_key,
      'Content-Type': 'application/json'
    }

    payload = json.dumps({
      "body": str(datetime.now()), # send current time stamp as message content 
      "recipient": recv_peer,
      "path": path
    })

    send_response = requests.request("POST",
                                send_url,
                                headers=headers,
                                data=payload)
    
    if (send_response.status_code == 202): # 202: message sent successfully 
        print("Message sent successfully, ",
              "Status code:", send_response.status_code)       
    else:
        print("Could not send message, ", 
              "Status code:", send_response.status_code)
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
