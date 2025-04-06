# -*- coding: utf-8 -*-
"""
© Anas Abuzayed 2025

This module contains a collection of functions that are commonly used in the
model.
"""


import numpy as np
import pandas as pd


def calculate_nearest_bus(data, a, n):
    """
    Calculate the nearest bus for each entry in data using Haversine formula.

    Parameters:
    data : DataFrame
        Data containing 'latitude' and 'longitude' columns, (in radians)
    a : DataFrame
        DataFrame containing 'x', 'y', and 'bus' columns with bus coordinates, (in radians)
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
            distance = np.arccos(np.sin(a.y[i]) * np.sin(data.latitude[j]) + np.cos(a.y[i]) *
                                 np.cos(data.latitude[j]) * np.cos(a.x[i] - data.longitude[j])) * R
            distances.append(distance)
        
        df = pd.DataFrame({'bus': a.bus, 'distance': distances})
        
        # Keep only wanted buses for the specific carrier
        df = df[df['bus'].isin(wanted_buses)]
        df.index = range(len(df))
        
        # Find the nearest bus
        buses.append(df.bus[np.argmin(df.distance)])
    
    return pd.Series(buses)
