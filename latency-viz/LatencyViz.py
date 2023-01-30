# =============================================================================
# =============================================================================
# Latency Visualization 
# =============================================================================
# =============================================================================

# =============================================================================
# Import Packages and Basic Setup  
# =============================================================================

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os 
import scipy.stats as stats

# Disable default warnings 
pd.options.mode.chained_assignment = None  # default='warn'

# Set print options (i.e. no scientific notation)
np.set_printoptions(suppress=True) 

# Change the current working directory
# os.chdir('C:\\Users\\beneb\\Desktop\\Research\\Latency')

# Print the current working directory
# vprint("Current working directory: {0}".format(os.getcwd()))

# Specifications for axis and title labels 
font1 = {'family':'sans-serif','color':'black','size':20}
font2 = {'family':'sans-serif','color':'black','size':20}

# =============================================================================
# Create Data from distribution   
# =============================================================================

# Normal Distribution
# --------------------
# --------------------
 
data_0 = np.random.normal(100, 50, 100)
data_1 = np.random.normal(300, 100, 100)
data_2 = np.random.normal(500, 150, 100)

data_0.mean(), data_1.mean(), data_2.mean() 

data = list([data_0, data_1, data_2])

# Truncated Normal Distribution (dont want to have latencies below 0)
# --------------------
# --------------------

# Define lower and upper truncation bound
# -------------------- 
a, b = 0, 1200 

# Define mean and sd (in ms) for each hop case and calculate the distribution 
# --------------------

# 1 HOP
mu_0, sigma_0 = 100, 50 
dist_0 = stats.truncnorm((a - mu_0) / sigma_0, (b - mu_0) / sigma_0, loc=mu_0, scale=sigma_0)

# 2 HOP
mu_1, sigma_1 = 300, 100 
dist_1 = stats.truncnorm((a - mu_1) / sigma_1, (b - mu_1) / sigma_1, loc=mu_1, scale=sigma_1)

# 3 HOP
mu_2, sigma_2 = 500, 150 
dist_2 = stats.truncnorm((a - mu_2) / sigma_2, (b - mu_2) / sigma_2, loc=mu_2, scale=sigma_2)


# draw samples from each distribution 
# -----------------

sample_size = 1000

data_0 = dist_0.rvs(sample_size)
data_1 = dist_1.rvs(sample_size)
data_2 = dist_2.rvs(sample_size)

data = list([data_0, data_1, data_2])

# Boxplot 
# --------------------
# --------------------

# Boxplot secifications 
boxprops = dict(linestyle='-', linewidth=1, color='black')
flierprops = dict(marker='o', markerfacecolor='none', markersize=6, markeredgecolor='black')
medianprops = dict(linestyle='-', linewidth=2, color='red')
meanpointprops = dict(marker='D', markeredgecolor='black', markerfacecolor='black')

fig, ax = plt.subplots()
fig.set_size_inches(14, 10)

# build a box plot
#plt.title("Latency", fontdict= font1)
plt.ylabel('Latency [ms]', fontdict = font2)
plt.xticks(fontsize=14)
plt.yticks(fontsize=14)
#plt.legend(loc='upper left')

ax.boxplot(data, showmeans=True, meanline=False, notch=False,
           boxprops=boxprops, flierprops=flierprops, medianprops=medianprops,
           meanprops=meanpointprops)
#ax.spines["right"].set_visible(False)
#ax.spines["top"].set_visible(False)
xticklabels=['1 HOP', '2 HOP', '3 HOP']
ax.set_xticklabels(xticklabels)
fig.savefig('Boxplot_latency.png')
