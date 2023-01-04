import random
import string
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.cm as cm
import matplotlib.colors as colors
import statistics

# Generate a random string to use as the name of the dictionary
name = ''.join(random.choices(string.ascii_letters, k=4))

# Create an empty dictionary with the name as the key
d = {name: {}}

# Generate 4 random strings of length 4
keys = [''.join(random.choices(string.ascii_letters, k=4)) for _ in range(4)]

# Add a list of 5 random numbers as the value for each key in the inner dictionary
for key in keys:
    d[name][key] = [random.randint(1, 10) for _ in range(5)]

print(d)

# The dictionary of dictionaries representing the graph
graph = {
    'Network 1': {
        'A': {},
        'B': {},
        'C': {},
        'D': {},
        'E': {}
    }
}

# Add all combinations of edges to the inner dictionary
for node1, connections1 in graph['Network 1'].items():
    for node2, connections2 in graph['Network 1'].items():
        # Skip self-edges
        if node1 == node2:
            continue
        # Add the edge to the inner dictionary
        graph['Network 1'][node1][node2] = [random.randint(1, 10) for _ in range(5)]

print(graph)

# Create an empty list to store the edge tuples
edges = []

# Extract the edge tuples and the edge attributes from the graph dictionary
for node, connections in graph['Network 1'].items():
    for connection, data in connections.items():
        # Compute the median value of the data
        median = statistics.median(data)
        # Add the median value to the edge attributes
        edges.append((node, connection, {'latency': data, 'median': median}))
                
# Create the graph using the from_dict_of_dicts method
G = nx.DiGraph()
G.add_edges_from(edges)  
      
# Set the color of each edge based on the median value of the data
edge_colors = []
for u, v, data in G.edges.data():
    median = data['median']
    # Use a color map to map the median value to a color
    color = plt.cm.RdYlGn(median / 10.0)
    edge_colors.append(color)
nx.set_edge_attributes(G, edge_colors, 'color')

# compute the degree of each node
degree = dict(G.degree(G.nodes()))

# Add the degree of each node as a node attribute
nx.set_node_attributes(G, degree, 'degree')

# Print the attributes of the nodes in the graph
for node, data in G.nodes.data():
    print(f'Node {node} has attributes {data}')

# Print the attributes of the edges in the graph
nx.get_edge_attributes(G, 'median')

# plot and save peer network 
plt.figure(figsize=(10, 10), dpi=100, frameon=True)

pos = nx.circular_layout(G)
color_map = ['red' if node == 'A' else 'yellow' for node in G]

nx.draw_networkx_nodes(G, pos, node_color=color_map, node_size=200, edgecolors='black')
nx.draw_networkx_edges(G, pos, width=0.8, connectionstyle="arc3,rad=0.1", edge_color=edge_colors)
nx.draw_networkx_labels(G, pos, labels=degree, font_size=10)

# Create a ScalarMappable to map the edge colors to a col
sm = cm.ScalarMappable(cmap=plt.cm.RdYlGn, norm=colors.Normalize(vmin=1, vmax=10))
sm.set_array([])

# Add a colorbar to the plot
cbar = plt.colorbar(sm, ticks=range(1, 11))
cbar.set_label('Latency', rotation=270, labelpad=20)

label_patch = mpatches.Patch(color='none', label='Labels represent node degrees')
plt.legend(handles=[label_patch], loc='upper left', frameon=False)

plt.axis('off')
plt.tight_layout()
plt.savefig("net_viz.pdf", pad_inches=0)
plt.show()





