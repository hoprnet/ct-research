# =============================================================================
# =============================================================================
# Estimate required size of the HOPR Network 
# =============================================================================
# =============================================================================

# =============================================================================
# Import Packages and Basic Setup  
# =============================================================================

import pandas as pd
#import matplotlib.pyplot as plt
#import matplotlib.dates as mdates
import numpy as np
import os 
#from datetime import datetime
import math as math 

# Disable default warnings 
pd.options.mode.chained_assignment = None  # default='warn'

# Set print options (i.e. no scientific notation)
np.set_printoptions(suppress=True) 

# Change the current working directory
os.chdir('C:\\Users\\beneb\\Desktop\\HOPR_Network')

# Print the current working directory
#vprint("Current working directory: {0}".format(os.getcwd()))

# Specifications for axis and title labels 
font1 = {'family':'sans-serif','color':'black','size':20}
font2 = {'family':'sans-serif','color':'black','size':20}

# =============================================================================
# Define Parameters   
# =============================================================================

# Ethereum Transactions
# ---------------------

# eth_tx = 1230386                # Avg Ethereum transactions per day (Period 1 Aug - 10 Aug)
eth_tx = 1000000
sec_per_day = 86400             # 60*60*24
tx_per_sec = eth_tx/sec_per_day # Transactions per second on ethereum 
tx_per_sec

# Payload of Ethereum Transactions
# ---------------------

payload = 1000 # bytes on average (need to measure this, but this is probably conservative)

# is there a relationship between gas_used for a transaction and bytes? 

# Network Packet Specification 
# ---------------------

MTU = 1480 # Maximum transmission unit (MTU) Hard limit of 1480 bytes, 
           # because you dont want to split up network packets on this level 

# HOPR Packet
# ---------------------
 
header = 400 # Header consists of 400 bytes. However, robert told me that this 
             # can be reduced in the future. 

body = 500   # Contains the payload. robert mentioned that 500 bytes are realistics 
             # However, up to a 1000 is possible with some work 

# HOPR Network
# ---------------------

# Node Capacity (Something we should measure!) - i.e. how many packets can a node process per second 
Node_Cap = 1 # packets per second. Conservative, I think 

# Network Capacity
Net_Size = [50, 75, 100] # Size of the HOPR network 

# Number of theoretical possible path
for i in Net_Size:
    print(math.factorial(i))

Net_Size = 50 
    
# Number of used path 
used_path = 50 # used path because we do not want to use all possible path 
                       
# =============================================================================
# Calculation    
# =============================================================================

# Bytes that need to be transferred per second
bytes_per_sec = tx_per_sec*payload   
bytes_per_sec

# Packets that need to be transferred per second 
packets_per_second = bytes_per_sec/body
packets_per_second

number_of_nodes = packets_per_second 

packets_per_day = packets_per_second*sec_per_day
packets_per_day

