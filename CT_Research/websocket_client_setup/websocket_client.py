# =============================================================================
# Access HOPR Node and Compute Latancy and Network Bandwidth 
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

# Change the current working directory
os.chdir('C:\\Users\\beneb\\Desktop\\Analytics\\Latency_Analysis')

# Print the current working directory
#vprint("Current working directory: {0}".format(os.getcwd()))

# Specifications for axis and title labels 
font1 = {'family':'sans-serif','color':'black','size':20}
font2 = {'family':'sans-serif','color':'black','size':20}


# Get a data report (can be disabled if sure about the origin) 
websocket.enableTrace(True)  

# =============================================================================
# Requests of Rest API using python   
# =============================================================================

# Set Parameters: Note that api_key, api_url and message_recipient change when setting up a new cluster 
api_key = 'adb01Cd949aC1b24c7CC4Da8#'
api_url = "https://zero_mekong_silver_phobos.playground.hoprnet.org:3001/api/v2/"
message_recipient = "16Uiu2HAmNcQGFqkoPQzfAEpp4u94YipRnyKGV5ckgpN9CiaZfkSu"
channel_info = api_url + "channels"
send_message = api_url + "messages"

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
