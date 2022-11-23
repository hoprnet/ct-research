# =============================================================================
# Access HOPR Node and Compute Latency and Network Bandwidth 
# =============================================================================

import json
import os 
import requests
import ssl
import sys
import websocket

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

    #
    # TODO: add code to validate that the API host is working
    #
    
    # get channel Information 
    channel_url = "https://{}:3001/api/v2/channels/".format(api_host)
    headers     = {
      'X-Auth-Token': api_key
    }
    response = requests.request("GET",
                                channel_url,
                                headers=headers)
    print(">>> Channel information <<<")
    print(json.dumps(response.json(), indent=4))
    
    # get peer ID of api_host 
    address_url = "https://{}:3001/api/v2/account/addresses".format(api_host)
    headers     = {
      'X-Auth-Token': api_key
    }
    response = requests.request("GET",
                                address_url,
                                headers=headers)
    print(">>> account peer ID information <<<")
    print(json.dumps(response.json(), indent=4))

    # send a message to ourselves
    send_url  = "https://{}:3001/api/v2/messages/".format(api_host)
    recv_peer = response.json()['hoprAddress']

    headers = {
      'X-Auth-Token': api_key,
      'Content-Type': 'application/json'
    }

    payload = json.dumps({
      "body": "Hello Ben",
      "recipient": recv_peer
    })

    response = requests.request("POST",
                                send_url,
                                headers=headers,
                                data=payload)
    print(response.status_code)
    sys.exit(1)

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
    ws = websocket.WebSocket(sslopt={"cert_reqs": ssl.CERT_NONE})
    ws.connect("wss://zero_mekong_silver_phobos.playground.hoprnet.org:3001/api/v2/messages/websocket?apiToken=adb01Cd949aC1b24c7CC4Da8%23")
    record  = ws.recv()
    print(record)
