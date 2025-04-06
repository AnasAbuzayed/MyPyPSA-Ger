# -*- coding: utf-8 -*-
"""
© Anas Abuzayed 2025

This module contains functions responsible for reading, filtering, correcting,
and processing input data for the PyPSA-based model, such as biomass data,
renewable profiles, coal corrections, etc.
"""

import os
import pandas as pd
import numpy as np
from math import pi
import logging
import json
import math
import requests
import time

#local imports
import Model_Code.utils as ut


logger = logging.getLogger(__name__)

def Biomass_data (n,name):
    """ Processes and corrects biomass power plant data in the network.

    This function reads biomass power plant data from a CSV file, filters, and processes it to update the network.
    It assigns the bus for each plant using geographic coordinates (NUTS) and adjusts capacities based on
    updated information. The function generates and saves data on biomass plants scheduled for removal
    and their corrected capacities.

    Parameters:
    -----------
    n : Network
        The network object to be updated with the corrected biomass data.
    
    name : str
        The directory path where the removal and addition data will be saved.

    Returns:
    --------
    pd.DataFrame
        A DataFrame containing the biomass plants scheduled for removal with their capacities.
    """
    
    
    if os.path.exists('{}/bio_basic_removal.csv'.format(name)):
        remove = pd.read_csv('{}/bio_basic_removal.csv'.format(name), index_col=0)
    else:
        data = pd.read_csv('data/renewable_power_plants_DE_bio.csv')
        data = data[['commissioning_date', 'decommissioning_date',
                     'technology', 'electrical_capacity', 'lat', 'lon', 'postcode']]
        data.columns = ['year_added', 'year_removed',
                        'carrier', 'p_nom', 'latitude',
                        'longitude', 'postcode']
        data.carrier = data.carrier.replace('Sewage and landfill gas', 'biomass')
        data.carrier = data.carrier.replace('Biomass and biogas', 'biomass')
        data.drop(data[data.carrier != 'biomass'].index, inplace=True)
        data.index = range(len(data))

        year_added = []
        year_removed = []
        for i in range(len(data)):
            year_added.append(int(data[data.columns[0]][i][:4]))
            year_removed.append(int(data[data.columns[0]][i][:4]) + 30)

        data.year_added = year_added
        data.year_removed = year_removed

        data.drop(data[data.year_added < 1989].index, inplace=True)
        data.drop(data[data.year_added > 2020].index, inplace=True)

        data.drop(data[np.isnan(data.longitude) == True].index, inplace=True)
        data.drop(data[np.isnan(data.latitude) == True].index, inplace=True)
        data.drop(data[np.isnan(data.p_nom) == True].index, inplace=True)
        data.drop(data[np.isnan(data.postcode) == True].index, inplace=True)

        data['bus'] = 0

        nuts_plz = pd.read_csv(os.path.join("data", "plz_nuts3.csv"),sep=';')
        nuts_plz['NUTS3'] = nuts_plz['NUTS3'].str.replace("'", '')
        nuts_plz['CODE'] = nuts_plz['CODE'].str.replace("'", '')
        nuts_plz['NUTS1'] = nuts_plz['NUTS3'].str[:3]  # Adjust NUTS code to match NUTS1
        nuts_plz['NUTS2'] = nuts_plz['NUTS3'].str[:4]  # Adjust NUTS code to match NUTS1

        for i in nuts_plz["NUTS1"].index:  # Adjust to match naming convention DE0 XYZ
            nuts_plz.loc[i, 'NUTS1'] = f'DE0 {nuts_plz.loc[i,"NUTS1"].split("DE")[1]}'

        cluster_key = pd.read_excel(\
                                    os.path.join(
                                        "data", f"cluster_key_{len(n.buses)}_clusters.xlsx"))

        for i in cluster_key.index:  # Adjust to match naming convention DE0 XYZ
            cluster_key.loc[i, 'Bus'] = f'DE0 {cluster_key.loc[i,"Bus"].split("DE")[-1]}'
            cluster_key.loc[i, 'NUTS'] = f'DE0 {cluster_key.loc[i,"NUTS"].split("DE")[-1]}'

        cluster_key.set_index('NUTS', inplace=True)

        for idx in data.index:  # aggregate buses to data
            plz = data.loc[idx, 'postcode']
            if len(str(int(plz))) == 5:  # make sure plz has correct format
                plz = str(int(data.loc[idx, 'postcode']))
                NUTS_region = nuts_plz.loc[nuts_plz['CODE'] == plz, 'NUTS1'].values[0]
                data.loc[idx, 'bus'] = cluster_key.loc[cluster_key.index == NUTS_region, 'Bus'].values[0]

            else:  # make sure plz has correct format
                plz = '0'+str(int(data.loc[idx, 'postcode']))
                NUTS_region = nuts_plz.loc[nuts_plz['CODE'] == plz, 'NUTS1'].values[0]
                data.loc[idx, 'bus'] = cluster_key.loc[cluster_key.index == NUTS_region, 'Bus'].values[0]

        data.index = range(len(data))
        # Removal
        removal = data[['year_removed', 'carrier', 'p_nom', 'bus']]
        years_res = list(removal.year_removed.value_counts().index)
        years_res.sort()
        remove = pd.DataFrame(columns=removal.columns)
        for i in years_res:
            dat = removal.loc[removal.year_removed == i]

            df = dat.groupby(['year_removed', 'bus', 'carrier']).sum().sum(
                level=['year_removed', 'bus', 'carrier']).unstack('year_removed').fillna(0).reset_index()

            df['year'] = [df.columns[2][1]]*len(df)
            df.columns = ['bus', 'carrier', 'p_nom', 'year_removed']
            remove = pd.concat([df, remove], ignore_index=False)

        remove.index = remove.bus + ' ' + remove.carrier
        remove.to_csv('{}/bio_basic_removal.csv'.format(name))

    correct = remove.groupby(['carrier', 'bus']).agg({'p_nom': ['sum']})
    correct = correct.stack().reset_index()
    correct = correct[['carrier', 'p_nom', 'bus']]
    correct.index = correct.bus + ' ' + correct.carrier

    for i in correct.index:
        try:
            n.generators.loc[i, 'p_nom']
        except:
            g = n.generators.loc[n.generators.carrier == 'biomass'].iloc[0]
            n.add("Generator", i,
                  bus=i[:5], marginal_cost=g.marginal_cost,
                  capital_cost=g.capital_cost, carrier=g.carrier,
                  efficiency=g.efficiency)
            logger.info(f"Adding {i} Generator")

        logger.info("Correcting {} capacity: {} MW instead of {} MW".format(i,
                                                                            round(correct.loc[i, 'p_nom'], 3),
                                                                            round(n.generators.loc[i, 'p_nom'], 3)))
        n.generators.loc[i, 'p_nom'] = correct.loc[i, 'p_nom']

    car='biomass'
    mo = set(n.generators.loc[n.generators.carrier == car, 'bus'])
    ac = set(remove.loc[remove.carrier == car, 'bus'])

    for item in list(mo.difference(ac)):
        n.remove('Generator', f'{item} {car}')
        logger.info(f"Removing {item} {car} Generator")


    addition = remove[['carrier', 'p_nom', 'bus']]
    addition.index = addition.bus + ' ' + addition.carrier
    add = addition.set_index(['carrier', 'bus']).stack().reset_index()
    add.columns = ['carrier', 'bus', 'remove', 'p_nom']
    add = add.groupby(['carrier', 'bus']).agg({'p_nom': ['sum']})
    bus = []
    carrier = []
    idx = []
    for i in add.index:
        carrier.append(i[0])
        bus.append(i[1])
        idx.append(i[1] + ' ' + i[0])

    add['carrier'] = carrier
    add['bus'] = bus
    add.index = idx
    add.columns = ['p_nom', 'carrier', 'bus']
    add.to_csv('{}/biomass_basic_addition.csv'.format(name))


    return remove

def RES_data(n,name):
    """
    Corrects renewable energy sources (RES) data and updates the network.

    This function processes CSV files with German renewable power plant data, correcting and classifying
    technologies, and mapping plants to the nearest bus in the network. It handles offshore wind data
    separately, differentiating between AC and DC connections. The function generates and saves data
    on new plant additions and those scheduled for removal, focusing on the period between 1995 and 2018.

    Parameters:
    -----------
    n : Network
        The network object to be updated with the corrected RES data.
    
    name : str
        The directory path where the addition and removal data will be saved.

    Returns:
    --------
    tuple of pd.DataFrame
        Returns two DataFrames: one for the added capacities and one for the removed capacities.
    """
        
    data=pd.read_csv('data/renewable_power_plants_DE.csv')
    data=data[['commissioning_date','decommissioning_date','technology','electrical_capacity','lat','lon']]
    data.columns=['year_added','year_removed','carrier','p_nom','latitude','longitude']
    data.carrier=data.carrier.replace('Photovoltaics', 'solar')
    data.carrier=data.carrier.replace('Onshore', 'onwind')
    data.carrier=data.carrier.replace('Photovoltaics ground', 'solar')
    data.carrier=data.carrier.replace('Run-of-river', 'ror')
    data.carrier=data.carrier.replace('Sewage and landfill gas', 'biomass')
    data.carrier=data.carrier.replace('Biomass and biogas', 'biomass')
    data.drop(data[data.carrier == 'biomass' ].index, inplace=True)

    """
    Change Offshore data
    """
    a=data[data.carrier=='Offshore']
    vals=pd.DataFrame({'lat_vals':a.latitude.unique()})
    vals.drop(vals[np.isnan(vals.lat_vals) ==True].index, inplace=True)
    a.latitude[np.isnan(a.latitude)]=vals.mean()[0]
    
    vals=pd.DataFrame({'long_vals':a.longitude.unique()})
    vals.drop(vals[np.isnan(vals.long_vals) ==True].index, inplace=True)
    
    a.longitude[np.isnan(a.longitude)] = np.random.choice(vals.long_vals,
                size=len(a.longitude[np.isnan(a.longitude)]))
    j=0
    for i in a.index:
        if a.carrier[i] == 'Offshore':
            j=j+1
            if j % 2 ==0:
                a.carrier[i]=('offwind-ac')
            else:
                a.carrier[i]=('offwind-dc')
    
    for i in a.index:
        data.loc[i,'carrier']=a.loc[i,'carrier']
        data.loc[i,'latitude']=a.loc[i,'latitude']
        data.loc[i,'longitude']=a.loc[i,'longitude']

    """ """

    data.index=range(len(data))
    
    year_added=[]
    year_removed=[]
    for i in range(len(data)):
        year_added.append( int(data[data.columns[0]][i][:4]) )
        year_removed.append( int(data[data.columns[0]][i][:4]) +25)
    
    data.year_added=year_added
    data.year_removed=year_removed
    
    data.drop(data[data.year_added < 1995 ].index, inplace=True)
    data.drop(data[data.year_added > 2018].index, inplace=True)
    data.drop(data[data.carrier == 'Other fossil fuels' ].index, inplace=True)
    data.drop(data[data.carrier == 'Geothermal' ].index, inplace=True)
    data.drop(data[data.carrier == 'Storage' ].index, inplace=True)
    
    
    data.drop(data[np.isnan(data.longitude) ==True].index, inplace=True)
    data.drop(data[np.isnan(data.latitude) ==True].index, inplace=True)
    data.drop(data[np.isnan(data.p_nom) ==True].index, inplace=True)
    

    
    data.drop(data[data.carrier=='ror'].index, inplace=True)
    data.drop(data[np.isnan(data.longitude) ==True].index, inplace=True)
    data.drop(data[np.isnan(data.latitude) ==True].index, inplace=True)
    data.index=range(len(data))

    ### 2019 data
    df2=pd.read_csv('data/renewable_power_plants_DE_2019.csv')
    df2=df2[['commissioning_date','decommissioning_date','technology','electrical_capacity','lat','lon']]
    df2.columns=['year_added','year_removed','carrier','p_nom','latitude','longitude']
    df2.carrier=df2.carrier.replace('Photovoltaics', 'solar')
    df2.carrier=df2.carrier.replace('Onshore', 'onwind')
    df2.carrier=df2.carrier.replace('Photovoltaics ground', 'solar')
    df2.carrier=df2.carrier.replace('Run-of-river', 'ror')
    df2.carrier=df2.carrier.replace('Sewage and landfill gas', 'biomass')
    df2.carrier=df2.carrier.replace('Biomass and biogas', 'biomass')
    df2.drop(df2[df2.carrier == 'biomass' ].index, inplace=True)

    # Correct offiwnd
    a_19=df2[df2.carrier=='Offshore']
    vals=pd.DataFrame({'lat_vals':a.latitude.unique()})
    vals.drop(vals[np.isnan(vals.lat_vals) ==True].index, inplace=True)
    a_19.latitude[np.isnan(a_19.latitude)]=vals.mean()[0]
    
    vals=pd.DataFrame({'long_vals':a.longitude.unique()})
    vals.drop(vals[np.isnan(vals.long_vals) ==True].index, inplace=True)
    
    a_19.longitude[np.isnan(a_19.longitude)] = np.random.choice(vals.long_vals,
                size=len(a_19.longitude[np.isnan(a_19.longitude)]))
    j=0
    for i in a_19.index:
        if a_19.carrier[i] == 'Offshore':
            j=j+1
            if j % 2 ==0:
                a_19.carrier[i]=('offwind-ac')
            else:
                a_19.carrier[i]=('offwind-dc')
    
    for i in a_19.index:
        df2.loc[i,'carrier']=a_19.loc[i,'carrier']
        df2.loc[i,'latitude']=a_19.loc[i,'latitude']
        df2.loc[i,'longitude']=a_19.loc[i,'longitude']
        
    
    df2.drop(df2[np.isnan(df2.longitude) ==True].index, inplace=True)
    df2.drop(df2[np.isnan(df2.latitude) ==True].index, inplace=True)
    df2.drop(df2[np.isnan(df2.p_nom) ==True].index, inplace=True)
    df2.drop(df2[df2.carrier == 'ror' ].index, inplace=True)
    df2.drop(df2[df2.carrier == 'Geothermal' ].index, inplace=True)
    
    
    df2.index=range(len(df2))
    
    year_added=[]
    year_removed=[]
    for i in range(len(df2)):
        year_added.append( int(df2[df2.columns[0]][i][:4]) )
        year_removed.append( int(df2[df2.columns[0]][i][:4]) +25)

    df2.year_added=year_added
    df2.year_removed=year_removed    
    
    data=pd.concat([data,df2])
    data.index=range(len(data))
    
    
    """" Mapping """
    data['bus']=data.latitude*0
    a=n.buses[['x','y']]
    a['bus']=a.index
    a.index=range(len(a))
    a.y*=pi/180
    a.x*=pi/180
    data.longitude*=pi/180
    data.latitude*=pi/180
    """"""
    
    data['bus'] = ut.calculate_nearest_bus(data, a, n)
    
    addition=data[['carrier','p_nom','bus']]
    addition.index=addition.bus + ' ' + addition.carrier
    add=addition.set_index(['carrier','bus']).stack().reset_index()
    add.columns=['carrier','bus','remove','p_nom']
    add=add.groupby(['carrier','bus']).agg({'p_nom':['sum']})
    bus=[]
    carrier=[]
    idx=[]
    for i in add.index:
        carrier.append(i[0])
        bus.append(i[1])
        idx.append(i[1] + ' ' + i[0])
    
    add['carrier']=carrier
    add['bus']=bus
    add.index=idx
    add.columns=['p_nom','carrier','bus']
    add.to_csv('{}/res_basic_addition.csv'.format(name))
    
    #TODO : All in one, save time
    removal=data[['year_removed','carrier','p_nom','bus']]
    years_res=list(removal.year_removed.value_counts().index)
    years_res.sort()
    remove= pd.DataFrame(columns = removal.columns)    
    for i in years_res:
        dat=removal.loc[removal.year_removed == i]
    
        df = dat.groupby(['year_removed', 'bus','carrier']).sum().sum(
            level=['year_removed', 'bus','carrier']).unstack('year_removed').fillna(0).reset_index()
    
        df['year']=[df.columns[2][1]]*len(df)
        df.columns=['bus','carrier','p_nom','year_removed']
        remove= pd.concat([df, remove], ignore_index=False)
    
    remove.index= remove.bus + ' ' + remove.carrier
    remove.to_csv('{}/res_basic_removal.csv'.format(name))

    return add,remove

def Correct_coal(n, name):
    """
    Adjusts coal power plant capacities in the network using updated data.

    This function processes a CSV file with German power plant data, filtering for active coal plants,
    correcting commissioning years for retrofitted units, and calculating the nearest bus using geographic coordinates.
    It updates the network with corrected capacities and saves filtered data for plants scheduled for removal after 2020.

    Parameters:
    -----------
    n : Network
        The network object representing the power system to be updated.
    
    name : str
        The directory path where the filtered data will be saved.

    Returns:
    --------
    pd.DataFrame
        The filtered data on coal plants scheduled for removal.
    """

    data = pd.read_csv('data/conventional_power_plants_DE.csv')
    data = data[['capacity_net_bnetza', 'energy_source',
                 'commissioned', 'retrofit', 'status',
                 'lat', 'lon', 'postcode']]
    data = data.rename(columns={"capacity_net_bnetza": "p_nom", "energy_source": "carrier"})
    data.drop(data[data.carrier != 'Hard coal'].index, inplace=True)
    data.drop(data[data.status == 'shutdown'].index, inplace=True)
    data.carrier = data.carrier.replace('Hard coal', 'coal')
    data.index = range(len(data))

    for i in range(len(data)):
        if data.retrofit[i] > data.commissioned[i]:
            data.loc[i, 'commissioned'] = data.commissioned[i] + 20

    data.drop(data[data.commissioned < 1969].index, inplace=True)
    data['year_removed'] = data.commissioned + 50

    data.index = range(len(data))

    data['bus'] = data.lat*0

    nuts_plz = pd.read_csv(os.path.join("data", "plz_nuts3.csv"),sep=';')
    nuts_plz['NUTS3'] = nuts_plz['NUTS3'].str.replace("'", '')
    nuts_plz['CODE'] = nuts_plz['CODE'].str.replace("'", '')
    nuts_plz['NUTS1'] = nuts_plz['NUTS3'].str[:3]  # Adjust NUTS code to match NUTS1
    nuts_plz.drop('NUTS3', axis=1, inplace=True)

    for i in nuts_plz["NUTS1"].index:  # Adjust to match naming convention DE0 XYZ
        nuts_plz.loc[i, 'NUTS1'] = f'DE0 {nuts_plz.loc[i,"NUTS1"].split("DE")[1]}'

    cluster_key = pd.read_excel(\
                                os.path.join(
                                    "data", f"cluster_key_{len(n.buses)}_clusters.xlsx"))


    for i in cluster_key.index:  # Adjust to match naming convention DE0 XYZ
        cluster_key.loc[i, 'Bus'] = f'DE0 {cluster_key.loc[i,"Bus"].split("DE")[-1]}'

    cluster_key.reset_index(inplace=True)

    for i in cluster_key.index:  # Adjust code to match naming convention DE0 XYZ
        cluster_key.loc[i, 'NUTS'] = f'DE0 {cluster_key.loc[i,"NUTS"].split("DE")[-1]}'

    cluster_key.set_index('NUTS', inplace=True)

    def get_postcode_from_coords(lat, lon):
        """Fetches the postal code using the Nominatim API based on latitude and longitude."""
        url = f'https://nominatim.openstreetmap.org/reverse?format=json&addressdetails=1&lat={lat}&lon={lon}'
        try:
            response = requests.get(url, headers={'User-Agent': 'GeocodingScript/1.0'})
            response.raise_for_status()  # Raise an error for bad status codes
            data = response.json()

            # Attempt to fetch the postal code from the response
            if data and 'address' in data:
                if 'postcode' in data['address']:
                    return data['address']['postcode']
        except requests.exceptions.RequestException as e:
            print(f"Error fetching postal code for lat={lat}, lon={lon}: {e}")
        return None

    # Iterate through the data and update the 'bus' column
    for idx in data.index:  # aggregate buses to data
        plz = data.loc[idx, 'postcode']
        if plz in nuts_plz['CODE'].values:
            if len(str(int(plz))) == 5:  # make sure plz has correct format
                plz = str(int(data.loc[idx, 'postcode']))
                NUTS_region = nuts_plz.loc[nuts_plz['CODE'] == plz, 'NUTS1'].values[0]
                data.loc[idx, 'bus'] = cluster_key.loc[cluster_key.index == NUTS_region, 'Bus'].values[0]
            else:  # make sure plz has correct format
                plz = '0' + str(int(data.loc[idx, 'postcode']))
                NUTS_region = nuts_plz.loc[nuts_plz['CODE'] == plz, 'NUTS1'].values[0]
                data.loc[idx, 'bus'] = cluster_key.loc[cluster_key.index == NUTS_region, 'Bus'].values[0]
        else:
            # Use latitude and longitude to find the correct postcode
            lat, lon = data.loc[idx, 'lat'], data.loc[idx, 'lon']
            plz = get_postcode_from_coords(lat, lon)
            if plz:
                print(f"Found postcode {plz} for lat={lat}, lon={lon}")
                if plz in nuts_plz['CODE'].values:
                    NUTS_region = nuts_plz.loc[nuts_plz['CODE'] == plz, 'NUTS1'].values[0]
                    data.loc[idx, 'bus'] = cluster_key.loc[cluster_key.index == NUTS_region, 'Bus'].values[0]
                else:
                    print(f"Postcode {plz} found via Nominatim but not in nuts_plz.")
                    data.loc[idx, 'bus'] = None  # Handle as necessary
            else:
                print(f"Could not find a matching postcode for lat={lat}, lon={lon}")
                data.loc[idx, 'bus'] = None  # Handle as necessary

    data = data[['carrier', 'p_nom', 'bus', 'year_removed']]
    data = data[data.year_removed >= 2020]
    data.index = data.bus + ' ' + data.carrier

    correct = data.groupby(['carrier', 'bus']).agg({'p_nom': ['sum']})
    correct = correct.stack().reset_index()
    correct = correct[['carrier', 'p_nom', 'bus']]
    correct.index = correct.bus + ' ' + correct.carrier


    for i in correct.index:
        try:
            n.generators.loc[i, 'p_nom']
        except:
            g = n.generators.loc[
                n.generators.carrier == data.loc[i, 'carrier']]\
                .iloc[0]

            n.add("Generator", i,
                  bus=i[:5], marginal_cost=g.marginal_cost,
                  capital_cost=g.capital_cost, carrier=g.carrier,
                  efficiency=g.efficiency,
                  p_max_pu=n.generators_t.p_max_pu[g.name]
                  if data.loc[i, 'carrier'] == 'ror'
                  else 1)
            logger.info(f"Adding {i} Generator")

        logger.info("Correcting {} capacity: {} MW instead of {} MW".format(i,
                                                                            round(correct.loc[i, 'p_nom'], 3),
                                                                            round(n.generators.loc[i, 'p_nom'], 3)))
        n.generators.loc[i, 'p_nom'] = correct.loc[i, 'p_nom']
    car='coal'
    mo = set(n.generators.loc[n.generators.carrier == car, 'bus'])
    ac = set(data.loc[data.carrier == car, 'bus'])

    for item in list(mo.difference(ac)):
        n.remove('Generator', f'{item} {car}')
        logger.info(f"Removing {item} {car} Generator")

    data.to_csv('{}/coal_basic_removal.csv'.format(name))

    return data

def Base_Removal_Data(n,name):
    """
     Processes and filters power plant data to prepare for network adjustments.

    This function reads power plant data from a CSV file, filters out specific carriers, 
    modifies the dataset, and calculates the nearest bus for each plant using geographic coordinates.
    It adjusts capacity values for CCGT and OCGT plants and saves the processed data 
    as 'conventional_basic_removal.csv', focusing on plants scheduled for removal after 2020.

    Parameters:
    -----------
    n : Network
        The network object used to determine bus locations for the power plants.

    Returns:
    --------
    pd.DataFrame
        A DataFrame containing the processed power plant data with key attributes.

    """
    
    data = pd.read_csv(os.path.join("data", "ppl.csv"))

    df1 = data[data.carrier == 'hydro']
    df2 = data[data.carrier != 'hydro']
    df1.drop(df1[df1.technology != 'Run-Of-River'].index, inplace=True)
    data = pd.concat([df1, df2])

    data = data[['carrier', 'p_nom', 'lat', 'lon', 'yeardecommissioning',
                 'yearcommissioned', 'retrofit', 'postcode']]

    data.drop(data[data.carrier == 'nuclear'].index, inplace=True)
    data.drop(data[data.carrier == 'biomass'].index, inplace=True)
    data.drop(data[data.carrier == 'other'].index, inplace=True)
    data.drop(data[data.carrier == 'waste'].index, inplace=True)
    data.drop(data[data.carrier == 'storage technologies'].index, inplace=True)
    data.carrier = data.carrier.replace('hydro', 'ror')
    df = pd.DataFrame({'p_nom': data.p_nom, 'carrier': data.carrier})
    summation = df.groupby('carrier').sum()
    data.index = range(len(data))

    nuts_plz = pd.read_csv(os.path.join("data", "plz_nuts3.csv"),sep=';')
    nuts_plz['NUTS3'] = nuts_plz['NUTS3'].str.replace("'", '')
    nuts_plz['CODE'] = nuts_plz['CODE'].str.replace("'", '')
    nuts_plz['NUTS1'] = nuts_plz['NUTS3'].str[:3]  # Adjust NUTS code to match NUTS1
    nuts_plz.drop('NUTS3', axis=1, inplace=True)

    for i in nuts_plz["NUTS1"].index:  # Adjust to match naming convention DE0 XYZ
        nuts_plz.loc[i, 'NUTS1'] = f'DE0 {nuts_plz.loc[i,"NUTS1"].split("DE")[1]}'

    cluster_key = pd.read_excel(\
                                os.path.join(
                                    "data", f"cluster_key_{len(n.buses)}_clusters.xlsx"))

    for i in cluster_key.index:  # Adjust to match naming convention DE0 XYZ
        cluster_key.loc[i, 'Bus'] = f'DE0 {cluster_key.loc[i,"Bus"].split("DE")[-1]}'

    cluster_key.reset_index(inplace=True)

    for i in cluster_key.index:  # Adjust code to match naming convention DE0 XYZ
        cluster_key.loc[i, 'NUTS'] = f'DE0 {cluster_key.loc[i,"NUTS"].split("DE")[-1]}'

    cluster_key.set_index('NUTS', inplace=True)

    data['bus'] = data.lat*0

    data['postcode'] = data['postcode'].astype(int)
    data['postcode'] = data['postcode'].astype(str)

    for idx in data.index:  # aggregate buses to data
        plz = data.loc[idx, 'postcode']
        if len(str(int(plz))) == 5:  # make sure plz has correct format
            plz = str(int(data.loc[idx, 'postcode']))
            NUTS_region = nuts_plz.loc[nuts_plz['CODE'] == plz, 'NUTS1'].values[0]
            data.loc[idx, 'bus'] = cluster_key.loc[cluster_key.index == NUTS_region, 'Bus'].values[0]

        else:  # make sure plz has correct format
            plz = '0'+str(int(data.loc[idx, 'postcode']))
            NUTS_region = nuts_plz.loc[nuts_plz['CODE'] == plz, 'NUTS1'].values[0]
            data.loc[idx, 'bus'] = cluster_key.loc[cluster_key.index == NUTS_region, 'Bus'].values[0]
    temp = data['yeardecommissioning']
    data = data[['carrier', 'p_nom', 'bus', 'yearcommissioned', 'retrofit']]
    data['year_removed'] = temp
    data.drop(data[data.carrier == 'coal'].index, inplace=True)

    data.drop(data[data.year_removed <= 2020].index, inplace=True)

    # Manually Correcting CCGT & OCGT
    data.p_nom[data.carrier == 'CCGT'] *= 1.25921273
    data.p_nom[data.carrier == 'OCGT'] *= 1.25921273

    data.index = data.bus + ' ' + data.carrier

    data.to_csv('{}/conventional_basic_removal.csv'.format(name))

    data_temp = data.groupby(['carrier', 'bus'], as_index=False).p_nom.sum()
    data_temp.index = data_temp.bus + ' ' + data_temp.carrier

    for i in data_temp.index:
        try:
            n.generators.loc[i, 'p_nom']
        except:
            g = n.generators.loc[
                n.generators.carrier == data_temp.loc[i, 'carrier']]\
                .iloc[0]

            n.add("Generator", i,
                  bus=i[:5], marginal_cost=g.marginal_cost,
                  capital_cost=g.capital_cost, carrier=g.carrier,
                  efficiency=g.efficiency,
                  p_max_pu=n.generators_t.p_max_pu[g.name]
                  if data_temp.loc[i, 'carrier'] == 'ror'
                  else 1)
            logger.info(f"Adding {i} Generator")

        logger.info("Correcting {} capacity: {} MW instead of {} MW".format(
            i, round(data_temp.loc[i, 'p_nom'], 2),
            round(n.generators.loc[i, 'p_nom'], 2)))
        n.generators.loc[i, 'p_nom'] = data_temp.loc[i, 'p_nom']

    for car in data_temp.carrier.unique():
        mo = set(n.generators.loc[n.generators.carrier == car, 'bus'])
        ac = set(data_temp.loc[data_temp.carrier == car, 'bus'])

        for item in list(mo.difference(ac)):
            n.remove('Generator', f'{item} {car}')
            logger.info(f"Removing {item} {car} Generator")
    return data

def update_rens_profiles(n,reference_year,name):  

    """ Updates renewable energy profiles for solar and wind generators in the network.

    This function fetches data from the Renewables.ninja API for the specified year, storing the profiles 
    in 'gen_profiles.csv'. If the file exists, it updates missing generator profiles. The function includes 
    a delay between API requests to avoid rate limiting.

    Parameters:
    -----------
    n : Network
        The network object containing the generators.
    reference_year : int
        The year for which to fetch renewable energy data.
    name : str
        The directory path to save the 'gen_profiles.csv' file.

    Returns:
    --------
    None
    """
    
    token = '1cacc0c037ec8d41e4ed821bcd9d1ab673766aee'
    api_base = 'https://www.renewables.ninja/api/'
    
    s = requests.session()
    s.headers = {'Authorization': 'Token ' + token}
    
    if os.path.exists('{}/gen_profiles.csv'.format(name)):
        gen_profiles=pd.read_csv('{}/gen_profiles.csv'.format(name),index_col=0)
        gen_profiles.index =n.generators_t.p_max_pu.index
    else:
        gen_profiles= pd.DataFrame(index =n.generators_t.p_max_pu.index,
                                   columns=list(n.generators.index[(n.generators.carrier=='solar') |
                                                                   (n.generators.carrier=='onwind')]))
    args_wind = {
        'date_from': str(reference_year)+'-01-01',
        'date_to': str(reference_year)+'-12-31',
        'capacity': 1.0,
        'height': 101.5, # min:84, max:119, avg:101.5
        'turbine': 'Vestas V112 3000',
        'format': 'json'}
    args_solar = {
        'date_from': str(reference_year)+'-01-01',
        'date_to': str(reference_year)+'-12-31',
        'dataset': 'merra2',
        'capacity': 1.0,
        'system_loss': 0.1,
        'tracking': 0,
        'tilt': 35,
        'azim': 180,
        'format': 'json'
        }
    args = {'solar':args_solar, 'onwind':args_wind}
    urls= {'solar':'pv', 'onwind':'wind'}
    for tech in ['solar','onwind']:
        for i in n.generators.index[n.generators.carrier==tech]:
            if (i not in gen_profiles.columns) | (math.isnan(gen_profiles[i][0])):
                args[tech]['lat']=n.buses.loc[n.generators.loc[i,'bus'],'y']
                args[tech]['lon']=n.buses.loc[n.generators.loc[i,'bus'],'x']
                url = api_base + 'data/{}'.format(urls[tech])
                r = s.get(url, params=args[tech])
                parsed_response = json.loads(r.text)
                data = pd.read_json(json.dumps(parsed_response['data']), orient='index')
                resample_factor=int(8760/len(n.snapshots))
                gen_profiles[i]=data.electricity.resample('{}H'.format(resample_factor)).mean()
                gen_profiles.to_csv('{}/gen_profiles.csv'.format(name))
                time.sleep(15)




            