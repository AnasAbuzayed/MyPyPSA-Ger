import numpy as np
import pandas as pd


def calculate_nearest_bus(data, a, n):
    """
    Calculate the nearest bus for each entry in data using Great-Circle Distance.

    Parameters:
    data : DataFrame
        Data containing 'lat' and 'lon' columns.
    a : DataFrame
        DataFrame containing 'x', 'y', and 'bus' columns with bus coordinates.
    n : Network
        The network object, used to filter out only relevant buses for the given carrier.

    Returns:
    pd.Series
        A series containing the nearest bus for each location.
    """
    R = 6371  # mean earth radius in km
    buses = []
    for j in range(len(data)):
        distances = []
        wanted_buses = list(n.generators.bus[n.generators.carrier == data.carrier[j]])
        for i in range(len(a)):
            distance = np.arccos(np.sin(a.y[i]) * np.sin(data.lat[j]) + np.cos(a.y[i]) *
                                 np.cos(data.lat[j]) * np.cos(a.x[i] - data.lon[j])) * R
            distances.append(distance)
        
        df = pd.DataFrame({'bus': a.bus, 'distance': distances})
        
        # Keep only wanted buses for the specific carrier
        df = df[df['bus'].isin(wanted_buses)]
        df.index = range(len(df))
        
        # Find the nearest bus
        buses.append(df.bus[np.argmin(df.distance)])
    
    return pd.Series(buses)
