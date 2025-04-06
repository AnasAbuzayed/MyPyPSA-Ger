# -*- coding: utf-8 -*-
"""
© Anas Abuzayed 2025

This module contains extra constraints passed to 'pypsa.linopf.lopf'
The functions here are adapted from the original scripts of PyPSA-Eur 
to fit the purpose of myopic constraints on generators and links in the
case of MyPyPSA-Ger
"""
import logging
logger = logging.getLogger(__name__)
import numpy as np
import pandas as pd

from pypsa.linopf import (get_var, define_constraints,
                          linexpr, join_exprs)



def extra_functionality(n, snapshots):
    """
    Supplementary constraints passed to ``pypsa.linopf.network_lopf``.
    Adapted from the original scripts of PyPSA-Eur
    
    """
    opts = n.opts
    config = n.config
    if 'CCL' in opts and n.generators.p_nom_extendable.any():
        add_CCL_constraints(n, config)
    add_battery_constraints(n)
    add_hydrogen_constraints(n)

def add_battery_constraints(n):
    
    nodes = n.buses.index[n.buses.carrier == "battery"]
    if nodes.empty or ('Link', 'p_nom') not in n.variables.index:
        return
    link_p_nom = get_var(n, "Link", "p_nom")
    lhs = linexpr((1,link_p_nom[nodes + " charger"]),
                  (-n.links.loc[nodes + " discharger", "efficiency"].values,
                   link_p_nom[nodes + " discharger"].values))
    define_constraints(n, lhs, "=", 0, 'Link', 'charger_ratio')

def add_hydrogen_constraints(n):
    store_name=n.stores[n.stores.carrier=='H2'].index
    link_1_name= [elem for elem in n.links.index if 'fuel cell' in elem]
    link_2_name= [elem for elem in n.links.index if 'electrolysis' in elem]
    ratio2 = 168
    ratio1 = ratio2 * 0.58
    
    
    for bus in n.buses.index[n.buses.carrier=='AC']:
        fc= [elem for elem in link_1_name if bus in elem]
        st= [elem for elem in store_name if bus in elem]
        el= [elem for elem in link_2_name if bus in elem]

        d=get_var(n, "Store", "e_nom").loc[st[0]]
        s=get_var(n, "Link", "p_nom").loc[fc[0]]
        r=get_var(n, "Link", "p_nom").loc[el[0]]
    
        lhs= linexpr((1, d),(-ratio1,s))
        define_constraints(n, lhs, "==", 0, f'{bus}-FC')

        lhs= linexpr((1, d),(-ratio2,r))
        define_constraints(n, lhs, "==", 0, f'{bus}-EL')

def add_CCL_constraints(n, config):
    agg_p_nom_limits = config['scenario_settings'].get('agg_p_nom_limits')
    try:
        agg_p_nom_minmax = pd.read_csv(agg_p_nom_limits,
                                       index_col=0)
            
    except IOError:
        logger.exception("Need to specify the path to a .csv file containing "
                          "aggregate capacity limits per country in "
                          "config['electricity']['agg_p_nom_limit'].")
    # cc means country and carrier
    year=config['year']

    minimum = agg_p_nom_minmax[['carrier','min']].dropna()
    minimum.set_index('carrier',inplace=True)
    
    maximum = agg_p_nom_minmax[['carrier','max']].dropna()
    maximum.set_index('carrier',inplace=True)

    # Generators
    p_nom_per_cc_g = (pd.DataFrame(
                    {'p_nom': linexpr((1, get_var(n, 'Generator', 'p_nom'))),
                    'carrier': n.generators.carrier})
                    .dropna(subset=['p_nom'])
                    .groupby('carrier').p_nom
                    .apply(join_exprs))
    try:
        p_nom_per_cc_g.drop('H2',inplace=True)
    except:
        pass
    # Storage_Unit
    # cc means country and carrier
    if any(n.storage_units.p_nom_extendable == True):
        p_nom_per_cc_s = (pd.DataFrame(
                        {'p_nom': linexpr((1, get_var(n, 'StorageUnit', 'p_nom'))),
                        'carrier': n.storage_units.carrier})
                        .dropna(subset=['p_nom'])
                        .groupby(['carrier']).p_nom
                        .apply(join_exprs))

    else:
        temp=pd.DataFrame(columns=['p_nom'])
        p_nom_per_cc_s=temp.p_nom
    
    #Store: H2 
    if any(n.stores.e_nom_extendable == True):
                
        for link in n.links.index:
            if n.links.loc[link,'carrier'] not in ['DC', 'imports']:
                n.links.loc[link,'carrier'] = link.split()[-1]
        for carrier in n.links.carrier.unique():
            p_act=n.links.loc[n.links.carrier==carrier,'p_nom'].sum()
            try:
                # minimum.loc[carrier]+=p_act
                maximum.loc[carrier]+=p_act
            except:
                pass

        
        p_nom_per_cc_h=pd.DataFrame(
            {'p_nom': linexpr((1, get_var(n, 'Link', 'p_nom'))),
             'carrier': n.links.carrier,
             'name': n.links.index}
            ).dropna(subset=['p_nom']
                     ).groupby(['carrier']).p_nom.apply(join_exprs)
        
    else:
        temp=pd.DataFrame(columns=['p_nom'])
        p_nom_per_cc_h=temp.p_nom



    p_nom_per_cc = pd.concat([p_nom_per_cc_g,
                              p_nom_per_cc_s,
                              p_nom_per_cc_h], ignore_index=False)
    # Run in case of minimum expansion limit
    # if not minimum.empty:
    #     idxs=np.intersect1d (np.array(p_nom_per_cc.index),
    #                     np.array(minimum.index))
    #     # minimum.loc[idxs].to_excel('data/minimum_cc.xlsx')
    #     for tech in idxs:
    #         print(f'Applying Min CCL to {tech}')
    #     # p_nom_per_cc.loc[idxs].to_excel('data/p_nom_per_cc_min.xlsx')

    #     minconstraint = define_constraints(n, p_nom_per_cc.loc[idxs].values,
    #                                        '>=', minimum.loc[idxs].values, 'agg_p_nom', 'min')

    # year=config['year']
    if not maximum.empty:
        idxs=np.intersect1d (np.array(p_nom_per_cc.index),
                        np.array(maximum.index))
        print(f'{year}: Applying Max CCL to',", ".join([str(i) for i in idxs]))
        maxconstraint = define_constraints(n, p_nom_per_cc.loc[idxs].values,
                                           '<=', maximum.loc[idxs].values, 'agg_p_nom', 'max')


