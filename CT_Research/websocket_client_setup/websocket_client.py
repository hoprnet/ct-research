# =============================================================================
# Access HOPR Node and Compute Latency and Network Bandwidth 
# =============================================================================

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os 
import requests
import websocket
import json
import ssl

# Disable default warnings 
pd.options.mode.chained_assignment = None  # default='warn'

# Set print options (i.e. no scientific notation)
np.set_printoptions(suppress=True) 

# Specifications for axis and title labels 
font1 = {'family':'sans-serif','color':'black','size':20}
font2 = {'family':'sans-serif','color':'black','size':20}

# Get a data report (can be disabled if sure about the origin) 
websocket.enableTrace(True)


def _getenvvar(name: str) -> str:
    """
    Returns the string contained in environment variable `name` or None.
    """
    ret_value = None
    if os.getenv(name) is None:
        print("Environment variable", name, "not found")
    else:
        ret_value = os.getenv(name)
    return ret_value


if __name__ == "__main__":
    # =============================================================================
    # Requests of Rest API using python   
    # =============================================================================
    # read parameters from environment variables
    api_key = _getenvvar('HOPR_API_KEY')
    api_url = _getenvvar('HOPR_API_URL')
    channel_info = api_url + "channels"
    send_message = api_url + "messages"
    message_recipient = "16Uiu2HAmNcQGFqkoPQzfAEpp4u94YipRnyKGV5ckgpN9CiaZfkSu"

    # Get Channel Information 
    # -----------------------

    payload={}
    headers = {
      'x-auth-token': api_key
    }

    response = requests.request("GET", channel_info, headers=headers, data=payload)
    print(response.text)

    # Send Message to yourself  
    # -----------------------

    payload = json.dumps({
      "body": "Hello Ben",
      "recipient": message_recipient
    })
    headers = {
      'x-auth-token': api_key,
      'Content-Type': 'application/json'
    }

    response = requests.request("POST", send_message, headers=headers, data=payload)


    # =============================================================================
    # Stream incomming messages for a node     
    # =============================================================================

    # Set-up websocket client   
    ws = websocket.WebSocket(sslopt={"cert_reqs": ssl.CERT_NONE})
    ws.connect("wss://zero_mekong_silver_phobos.playground.hoprnet.org:3001/api/v2/messages/websocket?apiToken=adb01Cd949aC1b24c7CC4Da8%23")
    record  = ws.recv()
    print(record)
