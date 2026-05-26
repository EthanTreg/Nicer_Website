import numpy as np

def min_bin(min_value: int, data: np.ndarray):
    count = 0.0
    bins = np.array([0])
    if len(data) == 0: return np.array([0])
    if min_value <= 0: return np.arange(len(data) + 1)
    
    for i, bin_counts in enumerate(data):
        count += bin_counts
        if count >= min_value:
            bins = np.append(bins, i + 1)
            count = 0.0
            
    if bins[-1] != len(data):
        if len(bins) > 1:
            bins[-1] = len(data)
        else:
            bins = np.append(bins, len(data))
            
    return bins

data = np.array([1, 1, 1, 1, 1])
print(min_bin(2, data))
data = np.array([3, 1])
print(min_bin(2, data))
