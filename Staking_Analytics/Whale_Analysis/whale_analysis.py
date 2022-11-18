# =============================================================================
# =============================================================================
# Whale Analysis  
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
# import requests
# from datetime import datetime 

# Disable default warnings 
pd.options.mode.chained_assignment = None  # default='warn'

# Set print options (i.e. no scientific notation)
np.set_printoptions(suppress=True) 

# Change the current working directory
os.chdir('C:\\Users\\beneb\\Desktop\\Analytics\\Scrape_Data')

# Print the current working directory
#vprint("Current working directory: {0}".format(os.getcwd()))

# Specifications for axis and title labels 
font1 = {'family':'sans-serif','color':'black','size':20}
font2 = {'family':'sans-serif','color':'black','size':20}

# =============================================================================
# Set parameters  
# =============================================================================

season_start = 1666785600
season_end = 1674738000
stake = 10000000
factor_denominator = 1e12
base_apr = 793
total_boost = 20771

boost_calculation = (total_boost / 1e12 * 60 * 60 * 24 * 365) * 100
apr_calculation = (base_apr / 1e12 * 60 * 60 * 24 * 365) * 100

# total_boost = ((boost/100)/(60 * 60 * 24 * 365)) * 1e12

Senario_1 = ((season_end-season_start) * (base_apr * stake)) / factor_denominator 
Senario_2 = ((season_end-season_start) * (base_apr * stake + total_boost * 200000)) / factor_denominator 

# =============================================================================
# Test Calculation   
# =============================================================================


season_start = 1658836800
season_end = 1666785600
stake = 2259788.9413
factor_denominator = 1e12
base_apr = 3171
boost = 32

total_boost = ((boost/100)/(60 * 60 * 24 * 365)) * 1e12

Senario_1 = ((season_end-season_start) * (base_apr * stake)) / factor_denominator 
Senario_2 = ((season_end-season_start) * (base_apr * stake + total_boost * 150000)) / factor_denominator 
