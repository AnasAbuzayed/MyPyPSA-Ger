# -*- coding: utf-8 -*-
"""
© Anas Abuzayed 2025
This module provides functions for H2-Ready power plants
"""
import numpy as np

def H2_Mixing(n,i,H2_Ready,removal_data):
    
    if H2_Ready and i >= 2041:
        # perform only if H2-ready scenario, from 2040
        # stop investments in Gas input, update values of Gas_input yearly so that factor is accurate
        n.links.loc[n.links.carrier == 'Gas_input', 'p_nom_extendable'] = False
    
        # initial_capacity is CCGT capacity at 2020, removed is whatever is till {i} removed
    
        initial_capacity = removal_data.loc[removal_data.carrier == 'CCGT'].groupby(['bus']).sum()['p_nom']
    
        removed_cap = removal_data.loc[(removal_data.carrier == 'CCGT')
                                       &
                                       (removal_data.year_removed <= i)].groupby(['bus']).sum()['p_nom']
    
        # Gas_cap is whatever CCGT capacity is left at year {i}
        Gas_Capacity = initial_capacity.sub(removed_cap, fill_value=0)  # unit is GW electric/bus
        Gas_Capacity[Gas_Capacity < 0] = 0  # only for safety
    
        act_cap = (n.links.loc[n.links.carrier == 'CCGT', 'p_nom']*0.61)  # unit is GW electric/bus, hence the 0.61
        act_cap.index = act_cap.index.str.removesuffix(' CCGT')
    
        # factor is share of whatever CCGT already built capacity before 2020, over all capacity, assuming all new are H2-Ready capable
        p_max_pu_factor = Gas_Capacity.divide(act_cap, fill_value=0)
        p_max_pu_factor.replace(np.nan, 0, inplace=True)
    
        # factor is share of whatever CCGT already built capacity before 2020, over all capacity, assuming all new are H2-Ready only
        sidxs = n.links.loc[n.links.carrier == 'Gas_input'].index.str.removesuffix(' Gas_input')  # only for safety
        n.links.loc[n.links.carrier == 'Gas_input', 'p_max_pu'] = p_max_pu_factor.loc[sidxs].values

          
def H2_Ready_opex(n,total_support,element):
    eff=0.8 if element =='electrolysis' else 0.61
    ts=total_support/0.030003*eff
    # X Eur/kg H2 local production or in CCGT subsidy subsidy
    n.links.loc[[elem for elem in \
                 n.links.index if element in elem],'marginal_cost']=\
        ts


def H2_Ready_plus(n, total_support):
    if total_support==0 :
        return
    nb = len(n.buses.index[n.buses.carrier == 'AC'])
    ts = (total_support*1e3)/nb #MW to GW
    
    for link in n.links.index[n.links.carrier == 'CCGT']:
        n.links.loc[link, 'p_nom'] += ts/n.links.loc[link, 'efficiency']
        n.links.loc[link, 'p_nom_extendable'] = False
        c1 = n.links.bus1 == n.links.loc[link, 'bus0']
        c2 = n.links.bus0 == 'DE0 ' + link.split()[1] + ' H2'

        n.links.loc[(c1) & (c2), 'p_nom_extendable'] = False

        n.links.loc[(c1) & (c2), 'p_nom'] += ts/n.links.loc[link, 'efficiency']
