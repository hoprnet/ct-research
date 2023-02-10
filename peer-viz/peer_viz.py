# =============================================================================
# Visualize Peer Network of Api Host 
# =============================================================================

import json
import logging
import os 
import requests
import sys
import pandas as pd
import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import random


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
    address_url = "http://{}:3001/api/v2/account/addresses".format(api_host)
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
    print(my_pid)
    
    # get information about the api host's peers
    peer_url = "http://{}:3001/api/v2/node/peers?quality=0.5".format(api_host)
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
    
    # Log the length of api_host peers 
    logging.info("Number of Peers: {}".format(len(api_host_peers)))
    print("Number of Peers: {}".format(len(api_host_peers)))
        
    # send a meesage to ourselves through a random peer
    peerId  = random.choice(api_host_peers)
    send_url = "http://{}:3001/api/v2/node/ping/".format(api_host)
    headers  = {
      'X-Auth-Token': api_key,
      'Content-Type': 'application/json'
    }
    logging.info("Ping: {}".format(peerId))

    payload = json.dumps({ 
      "peerId": peerId,
    })

    ping_response = requests.request("POST",
                                     send_url,
                                     headers=headers,
                                     data=payload)
    
    print("Ping Status Code: {}".format(ping_response.status_code))
    latency = json.dumps(ping_response.json()['latency'])
    print("Latency: {}".format(latency))
    logging.info("Latency: {}".format(latency))
    
    
    if (ping_response.status_code != 200): # 202: message sent successfully
        logging.error("Could not send message. Status code: {}".format(ping_response.status_code))
        sys.exit(1)
    
    sys.exit(1)
    
    # Get payment channel Information 
    channel_url = "http://{}:3001/api/v2/channels/".format(api_host)
    headers     = {
      'X-Auth-Token': api_key
    }
    channel_response = requests.request("GET",
                                channel_url,
                                headers=headers)
    
    if (channel_response.status_code != 200):
        logging.error("Could not fetch channel information. Status code: {}".format(channel_response.status_code))
        sys.exit(1)
    
    # convert channel response to dataframe 
    d = channel_response.json()
    df_edges = pd.concat([pd.DataFrame(v) for k,v in d.items()], keys=d)
    
    # create edge-dataframe by adding sender and receiver columns 
    df_edges.insert(0, 'sender', my_pid)
    df_edges = df_edges.rename(columns={'peerId': 'receiver'})
    df_edges = df_edges[['sender', 'receiver', 'type', 'channelId', 'status', 'balance']]
    df_edges["sender"] = np.where(df_edges['type'] == 'incoming', df_edges['receiver'], df_edges['sender'])
    df_edges["receiver"] = np.where(df_edges['type'] == 'incoming', my_pid, df_edges['receiver'])
    
    # create node-dataframe listing all unique peer id's including self 
    df_nodes=pd.DataFrame({'nodes':np.unique(df_edges[['sender', 'receiver']].values)})
    
    # save edge and node dataframe 
    df_edges.to_csv("edges.txt", index = False)  
    df_nodes.to_csv("nodes.txt", index = False)  
    
    # create a directed network graph 
    G = nx.from_pandas_edgelist(df_edges, 'sender', 'receiver', edge_attr=True, create_using=nx.DiGraph())

    # calculate degree and set as node attribute 
    degree = dict(G.degree(G.nodes()))
    in_degree = dict(G.in_degree(G.nodes()))
    out_degree = dict(G.out_degree(G.nodes()))

    nx.set_node_attributes(G, degree, 'degree')
    nx.set_node_attributes(G, in_degree, 'in_degree')
    nx.set_node_attributes(G, out_degree, 'out_degree')

    # plot and save peer network 
    plt.figure(figsize=(10, 10), dpi=100, frameon=True)

    pos = nx.circular_layout(G)
    color_map = ['red' if node == my_pid else 'yellow' for node in G]

    nx.draw_networkx_nodes(G, pos, node_color=color_map, node_size=200, edgecolors='black')
    nx.draw_networkx_edges(G, pos, width=0.5, connectionstyle="arc3,rad=0.1")
    nx.draw_networkx_labels(G, pos, labels=degree, font_size=10)
    
    label_patch = mpatches.Patch(color='none', label='Labels represent node degrees')
    plt.legend(handles=[label_patch], loc='upper left', frameon=False)

    plt.axis('off')
    plt.tight_layout()
    plt.savefig("peer_viz.png", pad_inches=0)
    
    sys.exit(1)

    
    