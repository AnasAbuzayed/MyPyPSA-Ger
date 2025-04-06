# -*- coding: utf-8 -*-
"""
© Anas Abuzayed 2025

This module provides functions for H2-Ready power plants
"""

import os
import pandas as pd
import pypsa
import logging
import numpy as np

logger = logging.getLogger(__name__)

def set_line_s_max_pu(n):
    """ set n-1 security margin to 0.5 for 37 clusters and to 0.7 from 200 clusters"""
    n_clusters = len(n.buses)
    s_max_pu = np.clip(0.5 + 0.2 * (n_clusters - 37) / (200 - 37), 0.5, 0.7)
    n.lines['s_max_pu'] = s_max_pu

def annuity(n, r):
    """
    Calculate the annuity factor for an asset with lifetime n years and
    discount rate of r, e.g. annuity(20,0.05)*20 = 1.6

    Parameters:
    n (int): The lifetime of the asset in years.
    r (float or pandas.Series): The discount rate. If a pandas.Series is provided, the annuity factor will be calculated for each element in the series.

    Returns:
    float or pandas.Series: The annuity factor(s) calculated based on the provided parameters.
    """

    if isinstance(r, pd.Series):
        return pd.Series(1/n, index=r.index).where(r == 0, r/(1. - 1./(1.+r)**n))
    elif r > 0:
        return r/(1. - 1./(1.+r)**n)
    else:
        return 1/n

def createFolder(directory):
    """Creates a folder if it doesn't exist.

    Parameters:
    -----------
    directory : str
        The path of the directory to create.

    Returns:
    --------
    None
    """

    try:
        if not os.path.exists(directory):
            os.makedirs(directory)
    except OSError:
        print ('Error: Creating directory. ' +  directory)

def update_availability_profiles(n,name):
    """
    Updates generator availability profiles using data from a CSV file.

    Parameters:
    -----------
    n : Network
        The network object to update.
    name : str
        The directory path containing the 'gen_profiles.csv' file.

    Returns:
    --------
    None
    """
    gen_profiles=pd.read_csv('{}/gen_profiles.csv'.format(name),index_col=0)
    for gen in gen_profiles.columns:
        logger.info("Correcting {} generation profile: {} CF instead of {}"
                    .format(gen,round(gen_profiles[gen].mean(),3),
                            round(n.generators_t.p_max_pu[gen].mean(),3)))
        n.generators_t.p_max_pu[gen]=gen_profiles[gen].values

def H2_ready(n,year,fuel_cost):
    """Prepares the network for hydrogen integration by adding hydrogen (H2) and hydrogen-natural gas (H2_NG) infrastructure.

    This function introduces the necessary components for hydrogen production, storage, and utilization,
    including buses, links, stores, and generators. It configures electrolysis, fuel cells, and hydrogen-gas mixing,
    and adjusts existing network elements to accommodate these technologies.

    Parameters:
    -----------
    n : Network
        The power system network to be updated.
    year : int
        The year when hydrogen integration begins.

    Returns:
    --------
    tuple of pd.DataFrame
        Two DataFrames tracking the capacity and lifecycle of hydrogen-ready components.
        """
    
    n.add("Carrier",'H2')
    n.add("Carrier",'H2_NG')
    names=[]
    for bus in n.buses.index[n.buses.carrier=='AC']:
        n.add("Bus", f"{bus} H2_NG",carrier='H2_NG',
              x=n.buses.loc[bus,'x'],
              y=n.buses.loc[bus,'y']) #H2-Gas Mix bus
        n.add("Link",f"{bus} Gas_input",
              bus0=f"{bus} gas",bus1=f"{bus} H2_NG",
              p_nom=n.links.loc[(n.links.bus1==bus)&(n.links.carrier=='CCGT'),'p_nom'],
              p_nom_extendable=True) #Gas input to Mix from gas store
        n.add("Bus", f"{bus} H2", carrier='H2',
              x=n.buses.loc[bus,'x'],
              y=n.buses.loc[bus,'y']) #H2 bus
        n.add("Store",  f"{bus} H2",
              bus= f"{bus} H2",carrier='H2',
              e_nom_extendable=True,
              capital_cost=264,
              e_cyclic_per_period=False
              )
        n.add("Generator",f"{bus} H2 import",carrier='H2',
                    bus=f"{bus} H2",
                    marginal_cost = fuel_cost.loc[2020,'H2'],
                    p_nom_extendable=True,
                   ) # H2 imports from abroad

        n.add("Link", f"{bus} H2_input",
              bus0=f"{bus} H2",bus1=f"{bus} H2_NG",
              capital_cost=18892.8, #94464*0.2 20% of CCGT CAPEX
              p_nom_extendable=True) #H2 input from electrolyser
        
        n.add(
            "Link",
            f"{bus} electrolysis",
            bus0=f"{bus}",
            bus1=f"{bus} H2",
            capital_cost=147832,
            p_nom_extendable=True,
            efficiency=0.8,
        )
            
        n.add(
            "Link",
            f"{bus} fuel cell",
            bus0=f"{bus} H2",
            bus1=f"{bus}",
            capital_cost=95234.84, # 164198*0.58
            p_nom_extendable=True,
            efficiency=0.58,
        )
    
    
        n.links.loc[(n.links.bus0==bus + ' gas')
                &
                (n.links.carrier=='CCGT'),'bus0']=f"{bus} H2_NG"

        idx_el=n.links.loc[(n.links.bus0==bus)
                &
                (n.links.bus1==bus + ' H2')].index[0]
        
        idx_fc=n.links.loc[(n.links.bus1==bus)
                &
                (n.links.bus0==bus + ' H2')].index[0]

        idx_ext=n.links.loc[(n.links.bus0==f"{bus} H2")
                &
                (n.links.bus1==f"{bus} H2_NG")].index[0]
        
        names.append(idx_el)
        names.append(idx_fc)
        names.append(idx_ext)
        
        
    df_H2=pd.DataFrame({'p_nom':np.zeros(len(names)),
                     'year_added':[year]*len(names),
                     'year_removed':[year+20]*len(names)},
                    index=names)

    df_store=pd.DataFrame({'p_nom':np.zeros(len(n.stores.index)),
                     'year_added':[year]*len(n.stores.index),
                     'year_removed':[year+20]*len(n.stores.index)},
                    index=n.stores.index)

    
    indices=[elem for elem in df_H2.index if 'input' in elem]
    df_H2.loc[indices,'year_removed']+=20
    return df_H2,df_store

def convert_opt_to_conv(n,year,res_add,name, fuel_cost):
    """ Converts extendable generators in the network to conventional generators with fixed capacities.

    This function adds gas infrastructure, adjusts the capacities of renewable and conventional generators, 
    and reconfigures CCGT and OCGT technologies. It creates fixed generators for biomass and run-of-river plants, 
    and updates the network to reflect these changes.

    Parameters:
    -----------
    n : Network
        The power system network to update.
    year : int
        The year in which the conversion takes place.
    res_add : pd.DataFrame
        DataFrame containing additional renewable capacities to be added.
    name : str
        The directory path for saving any intermediate or final data.

    Returns:
    --------
    pd.DataFrame
        A DataFrame tracking the converted generators with their capacities.
    """
    n.add("Carrier",'gas',co2_emissions=0.187)
    for bus in n.buses.index[n.buses.carrier=='AC']:
        n.add("Bus", f"{bus} gas",carrier='gas',
              x=n.buses.loc[bus,'x'],y=n.buses.loc[bus,'y']) #Gas bus
        n.add("Generator",f"{bus} Gas import",carrier='gas',
                    bus=f"{bus} gas",marginal_cost = fuel_cost.loc[2020,'gas'],
                    p_nom=1e9
                   ) # Gas imports 

    idx=[]
    bus=[]
    opt_p=[]
        
        
    for i in range(len(n.generators[n.generators.p_nom_extendable==True].index)):
        idx.append(n.generators[n.generators.p_nom_extendable==True].index[i])
        bus.append(n.generators[n.generators.p_nom_extendable==True].bus[i])
        opt_p.append(0)#n.generators[n.generators.p_nom_extendable==True].p_nom_opt[i]
    df=pd.DataFrame({'bus':bus,'p_nom':opt_p,'year_added':[year]*len(opt_p),'year_removed':[year+25]*len(opt_p)})
    df.index=idx
    
    c=pd.read_csv('{}/conventional_basic_removal.csv'.format(name), index_col=0)
    c=c[['carrier','p_nom','bus']]
    c.drop(c[c.carrier =='biomass'].index, inplace=True)
    c.drop(c[c.carrier =='coal'].index, inplace=True)
    c.drop(c[c.carrier =='lignite'].index, inplace=True)
    c.drop(c[c.carrier =='ror'].index, inplace=True)
    c.drop(c[c.carrier =='oil'].index, inplace=True)
    c=c.groupby(['carrier','bus']).agg({'p_nom':['sum']})
    c=c.stack().reset_index()
    c=c[['carrier','p_nom','bus']]
    c.index=c.bus + ' ' + c.carrier
    c.to_csv('{}/extendable_base_addition.csv'.format(name))
    p_max=0
    Value=0
    for i in range(len(df.index)):
        if idx[i] in n.generators_t.p_max_pu.columns:
            print('Renewable Extendable: This is executed for {}'.format(idx[i]))
            y2=list(n.generators_t.p_max_pu[idx[i]])

            g=n.generators.loc[n.generators.index == idx[i]].copy()
            if g.carrier[0] != 'ror':
                if idx[i] in res_add.index:
                    Value=res_add.p_nom[idx[i]]
                    p_max=g.p_nom_max[0]
                    if p_max <0:
                        p_max=0
                else:
                    Value=0
#                y1=y2*Value
                if Value >=p_max:
                    Value=p_max
                n.generators.loc[idx[i], 'p_nom_max']-= Value
                n.add("Generator","Fixed " + idx[i],
                      bus=g.bus[0],p_nom=Value,p_nom_opt=0,marginal_cost=g.marginal_cost[0],
                      capital_cost=0, carrier=g.carrier[0],p_nom_extendable=False,
                      p_nom_max=p_max,control=g.control[0],
                      efficiency=g.efficiency[0], p_min_pu=0, p_max_pu=y2)
                n.generators.loc["Fixed " + idx[i],'weight']=g.weight[0]
                n.generators_t.p["Fixed " + idx[i]]=0

    for bus in n.buses.index[n.buses.carrier=='AC']:
        for tech in ['CCGT','OCGT']:
            if bus + ' ' + tech in c.index:
                Value=c.loc[bus + ' ' + tech,'p_nom']
            else:
                Value=0

            try:
                g=n.generators.loc[(n.generators.bus== bus)
                                   &
                                   (n.generators.carrier==tech)]
                n.remove('Generator',bus + ' ' + tech)
                n.add("Link",name=bus + ' ' + tech,
                      bus0=f"{bus} gas",bus1=bus,
                      p_nom=Value/0.61 if tech =='CCGT' else Value/0.40,
                      carrier=tech,
                      efficiency=0.61 if tech =='CCGT' else 0.40,
                      p_nom_extendable=True,
                      capital_cost=g.capital_cost[0]*0.61 if tech =='CCGT' \
                          else g.capital_cost[0]*0.40,
                      marginal_cost=4.4*0.61 if tech=='CCGT' \
                      else 4.5*0.40)
            except:
                n.add("Link",name=bus + ' ' + tech,
                      bus0=f"{bus} gas",bus1=bus,
                      p_nom=Value/0.61 if tech =='CCGT' else Value/0.40,
                      carrier=tech,
                      efficiency=0.61 if tech =='CCGT' else 0.40,
                      p_nom_extendable=True,
                      capital_cost=94469*0.61 if tech =='CCGT' \
                          else 42234.56*0.40,
                      marginal_cost=4.4*0.61 if tech=='CCGT' \
                      else 4.5*0.40)
            


    for i in n.generators.index:
        n.generators.loc[i,'p_nom_opt']=0
    
    
    # Biomass & ROR
    cap_bio= ((annuity(30, 0.07) +
                             3.6/100.) *
                             2350*1e3 * 1)
    cap_ror= ((annuity(80, 0.07) +
                             2/100.) *
                             2500*1e3 * 1)

    for idx in n.generators.index[(n.generators.carrier=='biomass') | (n.generators.carrier=='ror')]:
        n.generators.loc[n.generators.index == idx,'capital_cost']= cap_bio if idx.split()[-1] == 'biomass' else cap_ror
        g=n.generators.loc[n.generators.index == idx].copy()
        n.add("Generator","Fixed " + idx,
              bus=g.bus[0],p_nom=g.p_nom[0],p_nom_opt=0,marginal_cost=g.marginal_cost[0],
              capital_cost=0, carrier=g.carrier[0],p_nom_extendable=False,
              p_nom_max=0,efficiency=g.efficiency[0])
        n.generators_t.p["Fixed " + idx]=0
        n.generators.loc[n.generators.index == idx,'p_nom_max']=0
        n.generators.loc[n.generators.index == idx,'p_nom_extendable']=True
        n.generators.loc[n.generators.index == idx,'p_nom']=0
        n.generators.loc[n.generators.index == idx,'p_nom_opt']=0

        if g.carrier[0] == 'ror':
            y2=list(n.generators_t.p_max_pu[g.index[0]])
            n.generators_t.p_max_pu['Fixed '  + idx] = y2
    return df

def convert_opt_storage_to_conv(n,year):
    """ Converts extendable storage units in the network to fixed-capacity storage units.

    This function identifies extendable storage units, fixes their capacities based on 
    optimization results, and adds them as non-extendable storage units in the network.
    The converted storage units retain their operational characteristics.

    Parameters:
    -----------
    n : Network
        The power system network to update.
    year : int
        The year in which the conversion takes place.

    Returns:
    --------
    pd.DataFrame
        A DataFrame tracking the converted storage units with their capacities.
    """

    idx=[]
    bus=[]
    opt_p=[]
    for i in range(len(n.storage_units[n.storage_units.p_nom_extendable==True].index)):
        idx.append(n.storage_units[n.storage_units.p_nom_extendable==True].index[i])
        bus.append(n.storage_units[n.storage_units.p_nom_extendable==True].bus[i])
        opt_p.append(n.storage_units[n.storage_units.p_nom_extendable==True].p_nom_opt[i])#n.generators[n.generators.p_nom_extendable==True].p_nom_opt[i]
    df=pd.DataFrame({'bus':bus,'p_nom':opt_p,'year_added':[year]*len(opt_p),'year_removed':[year+15]*len(opt_p)})
    df.index=idx
    
    for i in range(len(df.index)):
        print('Storage Extendable: This is executed for {}'.format(idx[i]))

        g=n.storage_units.loc[n.storage_units.index == idx[i]].copy()
        Value=df.p_nom[idx[i]]
        n.add("StorageUnit","Fixed " + idx[i],
              bus=g.bus[0],p_nom=Value,p_nom_opt=0,marginal_cost=g.marginal_cost[0],
              capital_cost=0, max_hours=g.max_hours[0], carrier=g.carrier[0],p_nom_extendable=False,
              p_nom_max=g.p_nom_max[0],control=g.control[0], p_min_pu=g.p_min_pu[0],
              efficiency_dispatch=g.efficiency_dispatch[0] , efficiency_store=g.efficiency_store[0],
              cyclic_state_of_charge=g.cyclic_state_of_charge[0] )
        
        n.storage_units_t.p_store["Fixed " + idx[i]]=n.storage_units_t.p_store[ idx[i]]*0
        n.storage_units_t.p_dispatch["Fixed " + idx[i]]=n.storage_units_t.p_dispatch[ idx[i]]*0

## TODO: Add Max hours to n.storage_units
    for i in n.storage_units.index:
        n.storage_units.loc[i,'p_nom_opt']=0
    return df