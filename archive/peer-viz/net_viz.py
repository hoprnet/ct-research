# =============================================================================
# Network visualization 
# =============================================================================

import random
import string
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.cm as cm
import matplotlib.colors as colors
import statistics
import numpy as np
import sys

# generate any number of random dictionaries 
# Note: These dictionaries will be importet (only for illustration)
num_dicts = 5
num_keys = 4
num_latency = 5
for i in range(1,num_dicts+1):
    locals()["dict_"+str(i)] = {''.join(random.sample(string.ascii_letters, 4)):
                               [random.randint(100, 1000) for _ in range(num_latency)] for _ in range(num_keys)}

# generate list of random names (i.e. peer_id of the api_hosts)       
# Note: The list of names will be importet (only for illustration)
names = [''.join(random.sample(string.ascii_letters, 4)) for _ in range(num_dicts)]

# example for main api_host (i.e. colored differently than the others) 
main_api_host = names[0]

# include names as the name key (i.e. the peer_id's of the api_hosts)
for i in range(1,num_dicts+1):
    locals()["dict_"+str(i)] = { names[i-1]: locals()["dict_"+str(i)] }        
        
# create a list of dictionaries 
dicts = []
for i in range(1, num_dicts+1):
    dicts.append(eval("dict_"+str(i)))
    
# Combine a list of dictionaries into a single dictionary 
combined = {k: v for d in dicts for k, v in d.items()}

# Create a graph dictionary
graph = {'Network': combined} 
graph = dicts[0]
print(graph)

# Create an empty list to store the edge tuples
edges = []

# Extract the edge tuples and the edge attributes from the graph dictionary
for node, connections in graph.items():
    for connection, data in connections.items():
        # Compute the median value of the data
        median = statistics.median(data)
        # Add the median value to the edge attributes
        edges.append((node, connection, {'latency': data, 'median': median}))
                
# Create the directed graph 
G = nx.DiGraph()
G.add_edges_from(edges)  
      
# Set the color of each edge based on the median value of the data
edge_colors = []
for u, v, data in G.edges.data():
    median = data['median']
    # Use a color map to map the median value to a color
    color = plt.cm.RdYlGn(median / 1000.0) 
    edge_colors.append(color)
nx.set_edge_attributes(G, edge_colors, 'color')

# compute the degree of each node
degree = dict(G.degree(G.nodes()))

# Add the degree of each node as a node attribute
nx.set_node_attributes(G, degree, 'degree')

# Print the attributes of the nodes in the graph
# for node, data in G.nodes.data():
#    print(f'Node {node} has attributes {data}')

# Print the attributes of the edges in the graph
# nx.get_edge_attributes(G, 'median')

# plot and save peer network 
plt.figure(figsize=(10, 10), dpi=100, frameon=True)

pos = nx.spring_layout(G)
#pos = nx.circular_layout(G)
color_map = ['red' if node == names[1] else 'yellow' for node in G]

nx.draw_networkx_nodes(G, pos, node_color=color_map, node_size=200, edgecolors='black')
nx.draw_networkx_edges(G, pos, width=1, connectionstyle="arc3,rad=0.1", edge_color=edge_colors)
nx.draw_networkx_labels(G, pos, labels=degree, font_size=10)

# Create a ScalarMappable to map the edge colors to a col
sm = cm.ScalarMappable(cmap=plt.cm.RdYlGn, norm=colors.Normalize(vmin=100, vmax=1000))
sm.set_array([])

# Add a colorbar to the plot
cbar = plt.colorbar(sm, ticks= np.linspace(100,1000,11)) 
cbar.set_label('Median Latency', rotation=270, labelpad=10)

label_patch = mpatches.Patch(color='none', label='Node labels represent node degrees')
plt.legend(handles=[label_patch], loc='upper left', frameon=False)

plt.axis('off')
plt.tight_layout()
plt.savefig("net_viz.pdf", pad_inches=0)
plt.savefig("net_viz.png", pad_inches=0)
plt.show()

sys.exit(1)

# =============================================================================
# Alternative plottting a complete graph 
# =============================================================================

# The dictionary of dictionaries representing the graph
graph = {
    'Network': {
        'A': {},
        'B': {},
        'C': {},
        'D': {},
        'E': {}
    }
}

# Add all combinations of edges to the inner dictionary
for node1, connections1 in graph['Network'].items():
    for node2, connections2 in graph['Network'].items():
        # Skip self-edges
        if node1 == node2:
            continue
        # Add the edge attributes to the inner dictionary
        graph['Network'][node1][node2] = [random.randint(100, 1000) for _ in range(5)]

print(graph)


