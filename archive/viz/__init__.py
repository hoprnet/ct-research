import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.cm as cm
import matplotlib.colors as colors
import numpy as np
import datetime

import matplotlib

# use the Matplotlib non-interactive backend, which allows Matplotlib to run without GUI
matplotlib.use("Agg")


def network_viz(graph: dict[str, dict[str, np.ndarray]], file_name: str):
    """
    Plots the received network graph, e.g.:

    graph = {'api_host': {'peerid_1': [50, 75, 100, 50, 75],
                        'peerid_2': [999, 900],
                        'peerid_3': [500, 500, 300, 400],
                        'peerid_4': [],
                        'peerid_5': [300, 400],
                        'peerid_6': [600]}}

    Optionally generated PNG called 'filename'.
    """
    edges = []
    max_val = 200.0

    # Extract the edge tuples and the edge attributes from the graph dictionary
    for node, connections in graph.items():
        for connection, data in connections.items():
            if len(data) == 0:
                median = np.nan
            else:
                median = np.median([d for d in data if d is not None])
            edges.append((node, connection, {"latency": data, "median": median}))

    # Create a directed graph
    G = nx.DiGraph()
    G.add_edges_from(edges)

    # Set the color of each edge based on the median value of the data
    edge_colors = []
    for u, v, data in G.edges.data():
        median = data["median"]

        # Use a color map to map the median value to a color
        color = plt.cm.RdYlGn_r(median / max_val)
        edge_colors.append(color)
    nx.set_edge_attributes(G, edge_colors, "color")

    # plot and save peer network
    plt.figure(figsize=(10, 10), dpi=100, frameon=True)

    pos = nx.spring_layout(G, seed=123)
    color_map = ["black" if node == "api_host" else "gray" for node in G]

    nx.draw_networkx_nodes(
        G, pos, node_color=color_map, node_size=200, edgecolors="black"
    )
    nx.draw_networkx_edges(
        G, pos, width=1, connectionstyle="arc3,rad=0.1", edge_color=edge_colors
    )

    # Create a ScalarMappable to map the edge colors to a col
    sm = cm.ScalarMappable(
        cmap=plt.cm.RdYlGn_r, norm=colors.Normalize(vmin=0, vmax=max_val)
    )
    sm.set_array([])

    # Add a colorbar to the plot
    cbar = plt.colorbar(sm, ticks=np.linspace(0, max_val, 11))
    cbar.set_label("Median Latency", rotation=270, labelpad=10)

    # Add Legend
    now = datetime.datetime.now()
    label = "Timestamp: {}".format(now.strftime("%Y-%m-%d %H:%M:%S"))
    label_patch = mpatches.Patch(color="none", label=label)
    plt.legend(handles=[label_patch], loc="upper left", frameon=False)

    plt.axis("off")
    plt.tight_layout()
    plt.savefig(file_name, pad_inches=0)

    #
    # discard the created image to save memory, see:
    #   http://stackoverflow.com/questions/21884271/ddg#21884375
    #
    plt.close()
