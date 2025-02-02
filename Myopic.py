"""
myopic.py

This module contains the 'myopic' or iterative approach functions that run year-by-year,
handling expansions, retirements, updates of costs, CO2 limits, and so on. It also
manages generator/line/storage phase-out or additional capacity to reflect a
time-evolving power system model.
"""

import pandas as pd
import numpy as np
import logging


def update_load(n,factor):
    """ Updates load values in the network by applying a multiplication factor.

    Parameters:
    -----------
    n : Network
        The network object containing load data.
    factor : float
        The factor by which to multiply the load values.

    Returns:
    --------
    None """
    # Look for Germany columns
    Germany_cols=[col for col in n.loads_t.p_set.columns if col.startswith('DE')]
    # Multiply by factor
    n.loads_t.p_set[Germany_cols]*=factor

def update_cost(n,year,cost_factors,fuel_cost):
    """
    Updates capital and fuel costs for technologies in the network for a specified year.

    Adjusts the capital costs of links, stores, generators, and storage units based on cost factors.
    Updates the marginal costs of generators by accounting for changes in fuel costs, considering 
    different fuels and generator efficiency.

    Parameters:
    -----------
    n : Network
        The network object to update.
    year : int
        The year for which costs are being updated.
    cost_factors : pd.DataFrame
        DataFrame containing cost adjustment factors for different technologies by year.
    fuel_cost : pd.DataFrame
        DataFrame with fuel costs for different technologies by year.

    Returns:
    --------
    None
    """
    
    #CAPEX
    
    for tech in cost_factors.columns:
        c=cost_factors[tech].loc[year]
        indices=[elem for elem in n.links.index if tech in elem]
        n.links.loc[indices,'capital_cost']*=c
        n.stores.loc[n.stores.carrier==tech,'capital_cost']*= c

        n.generators.loc[n.generators.carrier==tech,'capital_cost']*= c
        # n.generators.loc[n.generators.carrier==tech,'marginal_cost']*= c
        n.storage_units.loc[n.storage_units.carrier==tech,'capital_cost']*= c
        # n.storage_units.loc[n.storage_units.carrier==tech,'marginal_cost']*= c
        


#    n.generators.marginal_cost= n.generators.marginal_cost*0.99 ## TODO: Decrease only RES, seperate for carriers
    # Fuel
    # years = [int(item) for item in fuel_cost.columns]

    # for z in range(len(years[:-1])):
    #     if years[z] <= year < years[z+1]:
    #         spec_year=years[z]
    # if year == 2050:
    #     spec_year=years[z]
    
    #Fuel Cost:
    fuels=list(fuel_cost.columns)

    for tech in fuels:
        mask = (n.generators.carrier == tech) | (n.generators.carrier == f"imports_{tech}")
        if tech =='gas':
            
            old_cost=fuel_cost.loc[year-1,tech]
            new_cost=fuel_cost.loc[year,tech]
            n.generators.loc[mask,'marginal_cost']+=new_cost-old_cost

        elif tech=='H2':
            new_cost=fuel_cost.loc[year,tech]
            indices=[elem for elem in n.generators.index if tech in elem]
            n.generators.loc[indices,'marginal_cost']=new_cost
        else:
            eff = n.generators.loc[mask, 'efficiency'].mean()
            old_cost=fuel_cost.loc[year-1,tech]/eff
            new_cost=fuel_cost.loc[year,tech]/eff
            n.generators.loc[mask, 'marginal_cost'] += (new_cost - old_cost)

def update_co2price(n,year,co2price):
    """Updates generator marginal costs based on CO2 price changes for a specified year.

    Adjusts the marginal costs of CO2-emitting generators by calculating the difference 
    in CO2 prices between the current and previous year. The adjustment is based on the 
    CO2 emissions of each carrier and, for non-gas carriers, the average efficiency.

    Parameters:
    -----------
    n : Network
        The network object to update.
    year : int
        The year for which the CO2 price update is applied.
    co2price : pd.DataFrame
        DataFrame containing CO2 prices by year.

    Returns:
    --------
    None
    """
    
    dif= co2price.loc[year].item() - co2price.loc[year-1].item()
    for carrier in list(n.carriers.index[n.carriers.co2_emissions >0]):
        if carrier =='gas':
            val=dif* n.carriers.loc[carrier].co2_emissions
            n.generators.loc[n.generators.carrier==carrier,'marginal_cost']+=val
        else:
            val=dif* n.carriers.loc[carrier].co2_emissions /\
                n.generators.loc[n.generators.carrier==carrier,'efficiency'].mean()
            n.generators.loc[n.generators.carrier==carrier,'marginal_cost']+=val

def update_co2limit(n, new_lim):
    """ Updates the CO2 emission limit for the network.

    Parameters:
    -----------
    n : Network
        The network object to update.
    new_lim : float
        The new CO2 emission limit to set.

    Returns:
    --------
    None
      """
    n.global_constraints.constant=float(new_lim)

def delete_old_gens(n,year,base):

    """ Reduces capacity or removes old generators and links based on the specified year.

    Adjusts the nominal capacity (p_nom) of generators and links that are scheduled for removal or reduction 
    in the given year. Handles different generator types, ensuring capacities do not fall below zero.

    Parameters:
    -----------
    n : Network
        The network object to update.
    year : int
        The year for which to adjust capacities.
    base : pd.DataFrame
        DataFrame containing generator and link removal schedules.

    Returns:
    --------
    None
    """
    
    wanted=base[{'bus','p_nom'}][base.year_removed==year].sum(axis=1)
    for i in range(len(wanted.index)):
        if wanted.index[i] in n.generators.index:
            if wanted.index[i].split()[-1] =='import':
                continue
            if wanted.index[i].split()[-1] in ['biomass','ror']:
                n.generators.loc[n.generators.index == wanted.index[i],'p_nom_max'] =+ wanted[i]
                val= n.generators.loc['Fixed ' + wanted.index[i],'p_nom'] - wanted[i]
                if val >= 0 :
                    n.generators.loc['Fixed ' + wanted.index[i],'p_nom']= val
                else:
                    n.generators.loc['Fixed ' + wanted.index[i],'p_nom'] = 0

            else:

                val= n.generators.loc[wanted.index[i], 'p_nom'] - wanted[i]
                if val >= 0 :               
                    n.generators.loc[wanted.index[i], 'p_nom']= val
                else:
                    n.generators.loc[wanted.index[i], 'p_nom'] = 0

    for i in range(len(wanted.index)):
        if wanted.index[i] in n.links.index:
            if 'CCGT' in wanted.index[i]:
                val = wanted[i]/0.61
                n.links.loc['DE0 ' + wanted.index[i].split()[1] + ' Gas_input','p_nom']-=val
            eff=n.links.loc[wanted.index[i],'efficiency']
            val=n.links.loc[wanted.index[i],'p_nom']-wanted[i]/eff
            if val >= 0 :               
                n.links.loc[wanted.index[i], 'p_nom']= val
            else:
                n.links.loc[wanted.index[i], 'p_nom'] = 0

def Phase_out(n,carrier, phase_year):
    """Calculates the phase-out schedule for a specific generator carrier.

    Determines the total nominal capacity (p_nom) of generators using the specified carrier
    and calculates the yearly reduction needed to phase out the carrier by the given phase year.

    Parameters:
    -----------
    n : Network
        The network object containing the generators.
    carrier : str
        The generator carrier to phase out (e.g., 'coal', 'gas').
    phase_year : int
        The target year by which the carrier should be fully phased out.

    Returns:
    --------
    pd.DataFrame
        DataFrame of relevant generators using the specified carrier.
    float
        The calculated yearly reduction amount in nominal capacity.
        """

    a=n.generators[n.generators.carrier==carrier]
    Total=a.p_nom.sum()
    Yearly = Total / (phase_year - 2020)
    dist = []
    for i in a.index:
        dist.append( Yearly* a.p_nom.loc[i] / Total)
    return a, Yearly


def remove_Phase_out (n,removal, yearly_value):
    """Reduces nominal capacity (p_nom) of generators during a phase-out process.

    Calculates and applies the yearly capacity reduction for each generator in the removal list,
    ensuring capacities do not fall below zero.

    Parameters:
    -----------
    n : Network
        The network object containing the generators.
    removal : pd.DataFrame
        DataFrame of generators to phase out, including their capacities.
    yearly_value : float
        The yearly reduction value applied to the generators' nominal capacities.

    Returns:
    --------
    None
    """
    
    for i in removal.index:
        remove=yearly_value* removal.p_nom.loc[i] / removal.p_nom.sum()
        val= n.generators.loc[i, 'p_nom'] - remove
        if val >= 1 :
            n.generators.loc[[i], 'p_nom']= val
        else:
            n.generators.loc[[i], 'p_nom'] = 0

def H2_Ready_plus(n,total_support):
    """ Enhances hydrogen-ready power plants by distributing additional support capacity across CCGT links.

    This function allocates the total support capacity proportionally across buses, increasing the 
    nominal capacity (p_nom) of CCGT links. It also ensures that both CCGT and associated hydrogen 
    links are non-extendable and adjusts their capacities accordingly.

    Parameters:
    -----------
    n : Network
        The power system network to be updated.
    total_support : float
        The total additional support capacity to be distributed.

    Returns:
    --------
    None
    """
    nb=len(n.buses.index[n.buses.carrier=='AC'])
    ts=total_support/nb
    
    for link in n.links.index[n.links.carrier=='CCGT']:
        n.links.loc[link,'p_nom']+=ts/n.links.loc[link,'efficiency']
        n.links.loc[link,'p_nom_extendable']=False
        c1= n.links.bus1==n.links.loc[link,'bus0']
        c2= n.links.bus0=='DE0 ' + link.split()[1] + ' H2'
        
        n.links.loc[(c1) & (c2),'p_nom_extendable']=False
        
        n.links.loc[(c1) & (c2),'p_nom']+=ts/n.links.loc[link,'efficiency']

def update_const_gens(n):
    """ Updates capacities of fixed generators and associated links in the network.

    This function adjusts the nominal capacities (p_nom) of 'Fixed' generators by adding their optimized capacities.
    For renewable generators like run-of-river and biomass, it decreases the p_nom_max of the original generators.
    It also ensures that the capacities of CCGT and OCGT links are updated if their optimized capacity exceeds the current capacity.
    Finally, it aligns the nominal capacity of gas input links with the updated capacities of CCGT generators.

    Parameters:
    -----------
    n : Network
        The network object containing the generators and links to update.

    Returns:
    --------
    None
    """
    for i in range(len(n.generators.index)):
        if n.generators.index[i][:5] =='Fixed':
            n.generators.loc[n.generators.index[i],'p_nom']+=n.generators.p_nom_opt[n.generators.index[i][6:]]

            if n.generators.index[i].split()[-1] in ['ror','biomass']:
                n.generators.loc[n.generators.index[i][6:],'p_nom_max'] -= n.generators.p_nom_opt[n.generators.index[i][6:]]
                # n.generators.p_nom_opt[n.generators.index[i][6:]] = 0 
            else:                        
                n.generators.loc[n.generators.index[i],'p_nom_max']-=n.generators.p_nom_opt[n.generators.index[i][6:]]
            if n.generators.p_nom_max[n.generators.index[i][6:]] < 0:
                n.generators.loc[n.generators.index == n.generators.index[i][6:], 'p_nom_max']=0

    for link in n.links.index[(n.links.carrier=='CCGT')
                              |
                              (n.links.carrier=='OCGT')]:
        if n.links.loc[link,'p_nom_opt'] > n.links.loc[link,'p_nom']:
            n.links.loc[link,'p_nom'] = n.links.loc[link,'p_nom_opt']
    n.links.loc[n.links.carrier=='Gas_input','p_nom'] = n.links.loc[n.links.carrier=='CCGT','p_nom'].values


def update_const_storage(n):
    """ Updates the capacities of fixed storage units in the network.

    For each storage unit labeled as 'Fixed,' this function increases the nominal capacity (p_nom) 
    by adding the optimized capacity (p_nom_opt) from the corresponding original storage unit.

    Parameters:
    -----------
    n : Network
        The network object containing the storage units to update.

    Returns:
    --------
    None
    """
    for i in range(len(n.storage_units.index)):
        if n.storage_units.index[i][:5] =='Fixed':
            n.storage_units.loc[n.storage_units.index[i],'p_nom']+=n.storage_units.p_nom_opt[n.storage_units.index[i][6:]]
    return 


def update_const_lines(n,year,df_H):
    """" Updates line and link capacities in the network to match their optimized values if they are higher.

    This function adjusts the capacities of network lines and specific hydrogen-related links (electrolysis, fuel cell, H2 input),
    as well as DC links, recording any changes in a temporary DataFrame. The updated DataFrame, including these capacity adjustments, is returned.

    Parameters:
    -----------
    n : Network
        The network object containing the lines and links to update.
    year : int
        The year in which the capacity updates are made.
    df_H : pd.DataFrame
        A DataFrame tracking previous capacity changes to be updated.

    Returns:
    --------
    pd.DataFrame
        An updated DataFrame including capacity adjustments for hydrogen-related and DC links.
    """

    for line in n.lines.index:
        if n.lines.loc[line,'s_nom_opt']>n.lines.loc[line,'s_nom']:
            n.lines.loc[line,'s_nom']=n.lines.loc[line,'s_nom_opt']
            
    #H2
    techs=['electrolysis','fuel cell','H2_input']
    indices=[]
    for tech in techs:
        indices.extend([elem for elem in n.links.index if tech in elem])
    
    temp=pd.DataFrame({'p_nom':0,
                  'year_added':year,
                  'year_removed':year+20},
                 index=indices)
    indices=[elem for elem in n.links.index if 'H2_input' in elem]
    temp.loc[indices,'year_removed']+=20

    for links in temp.index:
        if n.links.loc[links,'p_nom_opt']>n.links.loc[links,'p_nom']:
            v=abs(n.links.loc[links,'p_nom']-n.links.loc[links,'p_nom_opt'])
            n.links.loc[links,'p_nom']=n.links.loc[links,'p_nom_opt']
            temp.loc[links,'p_nom']=v

    for links in n.links.index[n.links.carrier=='DC']:
        if n.links.loc[links,'p_nom_opt']>n.links.loc[links,'p_nom']:
            n.links.loc[links,'p_nom']=n.links.loc[links,'p_nom_opt']
    
    return pd.concat([df_H,temp])

def Yearly_potential(n,saved_potential,regional_potential,agg_p_nom_minmax):
    """ Adjusts the yearly potential for generator capacities and updates the network accordingly.

    This function reduces the available capacity (saved_potential) for extendable generators based on their optimized capacity.
    It updates the maximum nominal capacity (p_nom_max) of generators and links, ensuring that capacities do not exceed the regional potential.
    The function also handles specific adjustments for CCGT, OCGT, and storage units.

    Parameters:
    -----------
    n : Network
        The network object containing generators, links, and storage units to update.
    saved_potential : pd.Series
        A series tracking the remaining potential for each generator.
    regional_potential : float
        The regional potential limit for generator capacities.

    Returns:
    --------
    pd.Series
        Updated series of saved potentials after adjustments.
        """
    
    for i in n.generators.index[n.generators.p_nom_extendable==True]:

        if i.split()[-1] =='import':
            continue
        if i.split()[-1] not in ['biomass','ror']:
            saved_potential[i]-=n.generators.p_nom_opt[i]
            if saved_potential[i] >= regional_potential:
                n.generators.loc[i,'p_nom_max']=regional_potential
            else:
                n.generators.loc[i,'p_nom_max']=saved_potential[i]
    for i in saved_potential.index:
        if saved_potential[i] <= 1:
            n.generators.loc[i,'p_nom_max']=0
            saved_potential[i]=0
    for i in n.generators.index[n.generators.p_nom_extendable==False]:
        n.generators.loc[i,'p_nom_max'] = 0 if n.generators.loc[i,'p_nom_max']<0 else  n.generators.loc[i,'p_nom_max']

    for i in n.links.index:
        if n.links.loc[i,'carrier'] in ['CCGT','OCGT']:
            condition = n.links.loc[i,'p_nom'] > n.links.loc[i,'p_nom_opt']
            val = n.links.loc[i,'p_nom'] if condition else n.links.loc[i,'p_nom_opt']
            eff=n.links.loc[i,'efficiency']
            n.links.loc[i,'p_nom_max']=val+ regional_potential/eff
    for i in n.storage_units.index[
            n.storage_units.p_nom_extendable==True]:
        l_b=len(n.buses[n.buses.carrier=='AC'])
        yp=agg_p_nom_minmax.loc['battery','max']
        n.storage_units.p_nom_max.loc[i]=regional_potential# yp/l_b*1.5 ##Rp for batteries
    return saved_potential

def append_gens(n,year,df):
    """ Appends new generators and links with their capacities and lifetimes to the tracking DataFrame.

    This function identifies extendable generators and CCGT/OCGT links in the network, calculates their optimized capacities,
    and determines their expected lifetimes. It then appends this information to the provided DataFrame.

    Parameters:
    -----------
    n : Network
        The network object containing the generators and links.
    year : int
        The current year, used to calculate the removal year of the components.
    df : pd.DataFrame
        The DataFrame to which the new generator and link information will be appended.

    Returns:
    --------
    pd.DataFrame
        The updated DataFrame with the appended generators and links.
    """

    idx=[]
    bus=[]
    opt_p=[]
    life=[]
    lifetime=pd.DataFrame({'carrier':['CCGT','OCGT','offwind-ac',
                                    'offwind-dc','onwind','solar','ror','biomass'],
                         'life':[30,30,25,25,25,25,80,30]})
    for i in n.generators[n.generators.p_nom_extendable==True].index:
        if i.split()[-1] == 'import':
            continue
        if i.split()[-1] not in ['biomass','ror']:
            idx.append(i)
            bus.append(n.generators.loc[i,'bus'])
            opt_p.append(n.generators.loc[i,'p_nom_opt'])
            life.append(year + lifetime.loc[lifetime.carrier==idx[-1].split()[-1], 'life'].item())
        else:
            idx.append(i)
            bus.append(n.generators.loc[i,'bus'])
            opt_p.append(n.generators.loc[i,'p_nom_opt'])
            life.append(year + lifetime.loc[lifetime.carrier==idx[-1].split()[-1], 'life'].item())

    for i in n.links.index:
        if i.split()[-1] in ['CCGT','OCGT']:
            idx.append(i)
            bus.append(n.links.loc[i,'bus1'])
            life.append(year + lifetime.loc[lifetime.carrier==idx[-1].split()[-1], 'life'].item())
            val=0
            ef=1
            if n.links.loc[i,'p_nom_opt'] > n.links.loc[i,'p_nom']:
                val= n.links.loc[i,'p_nom_opt'] - n.links.loc[i,'p_nom']
                ef = n.links.loc[i,'efficiency']
            opt_p.append(val*ef)


    temp=pd.DataFrame({'bus':bus,'p_nom':opt_p,'year_added':[year]*len(opt_p),'year_removed':life})
    temp.index=idx
    df = pd.concat([df, temp], ignore_index=False)
    return df

def append_storages(n,year,df,df_S):
    """ Appends new storage units and stores with their capacities and lifetimes to tracking DataFrames.

    This function identifies extendable storage units and stores in the network, calculates their optimized capacities,
    and determines their expected lifetimes. It appends this information to the provided DataFrames.

    Parameters:
    -----------
    n : Network
        The network object containing the storage units and stores.
    year : int
        The current year, used to calculate the removal year of the components.
    df : pd.DataFrame
        The DataFrame to which the new storage unit information will be appended.
    df_S : pd.DataFrame
        The DataFrame to which the new store information will be appended.

    Returns:
    --------
    tuple of pd.DataFrame
        The updated DataFrames with appended storage units and stores.
    """

    idx=[]
    bus=[]
    opt_p=[]
    for i in range(len(n.storage_units[n.storage_units.p_nom_extendable==True].index)):
        idx.append(n.storage_units[n.storage_units.p_nom_extendable==True].index[i])
        bus.append(n.storage_units[n.storage_units.p_nom_extendable==True].bus[i])
        opt_p.append(n.storage_units[n.storage_units.p_nom_extendable==True].p_nom_opt[i])
    temp=pd.DataFrame({'bus':bus,'p_nom':opt_p,'year_added':[year]*len(opt_p),'year_removed':[year+15]*len(opt_p)})
    temp.index=idx
    df = pd.concat([df, temp], ignore_index=False)
    
    d_n=pd.DataFrame({'p_nom':n.stores.loc[
        n.stores.e_nom_opt>n.stores.e_nom,'e_nom_opt'],
        'year_added':year,
        'year_removed':year+20})
    df_S=pd.concat([df_S,d_n])
    
    for s in n.stores[n.stores.e_nom_opt>n.stores.e_nom].index:
        n.stores.loc[s,'e_nom']+=n.stores.loc[s,'e_nom_opt']
    return df,df_S

def initial_storage(n):
    """ Updates the initial state of charge for storage units in the network.

    This function sets the initial state of charge of each storage unit to the final state of charge 
    from the previous time period.

    Parameters:
    -----------
    n : Network
        The network object containing the storage units.

    Returns:
    --------
    None
    """
    initial=n.storage_units.state_of_charge_initial.copy()
    last_state=n.storage_units_t.state_of_charge[n.storage_units_t.state_of_charge.index==n.storage_units_t.state_of_charge.index[-1]].copy()
    
    for i in last_state.columns:
        initial.loc[i]=last_state[i][0]

    n.storage_units.state_of_charge_initial=initial


def delete_gens(n,year,df):
    """ Reduces or removes generator capacities in the network based on a specified year.

    This function identifies generators and links scheduled for removal or capacity reduction in the given year
    and updates their nominal capacities (p_nom). For non-biomass and non-gas generators, it adjusts the 
    'p_nom' and 'p_nom_max' of the corresponding 'Fixed' generators. For OCGT and CCGT generators, it directly 
    adjusts the capacities of the associated links.

    Parameters:
    -----------
    n : Network
        The network object containing the generators and links to be updated.
    year : int
        The year in which the capacity adjustments or removals are applied.
    df : pd.DataFrame
        A DataFrame tracking the generator capacities and their removal schedules.

    Returns:
    --------
    None
    """
    wanted=df[{'bus','p_nom'}][df.year_removed==year]
    wanted=wanted.groupby(level=0).sum()
    for i in range(len(wanted.index)):
        if wanted.index[i].split()[-1] not in ['biomass','OCGT','CCGT']:
            n.generators.loc['Fixed ' + wanted.index[i], 'p_nom']-=wanted.loc[wanted.index[i],'p_nom']
            n.generators.loc['Fixed ' + wanted.index[i], 'p_nom_max']+=wanted.loc[wanted.index[i],'p_nom']
            saved_potential[wanted.index[i]]+=wanted.loc[wanted.index[i],'p_nom']
            if n.generators.loc[wanted.index[i], 'p_nom_max'] + wanted.loc[wanted.index[i],'p_nom'] < regional_potential:
                n.generators.loc[wanted.index[i], 'p_nom_max']+=wanted.loc[wanted.index[i],'p_nom']
            if n.generators.loc['Fixed ' + wanted.index[i], 'p_nom']<=0:
                n.generators.loc['Fixed ' + wanted.index[i], 'p_nom'] = 0
        elif wanted.index[i].split()[-1] in ['OCGT','CCGT']:
            n.links.loc[wanted.index[i], 'p_nom']-=wanted.loc[wanted.index[i],'p_nom']


def delete_storage(n,year,df,df_H,df_S):
    """ Reduces or removes storage capacities in the network based on a specified year.

    This function adjusts the nominal capacities (p_nom) of fixed storage units scheduled for removal
    in the given year. It also updates the capacities of hydrogen-related links and stores, ensuring 
    that no capacities fall below zero.

    Parameters:
    -----------
    n : Network
        The network object containing the storage units, links, and stores to be updated.
    year : int
        The year in which the capacity adjustments or removals are applied.
    df : pd.DataFrame
        A DataFrame tracking the storage unit capacities and their removal schedules.
    df_H : pd.DataFrame
        A DataFrame tracking the capacities and removal schedules for hydrogen-related links.
    df_S : pd.DataFrame
        A DataFrame tracking the capacities and removal schedules for hydrogen stores.

    Returns:
    --------
    None
    """

    wanted=df[{'bus','p_nom'}][df.year_removed==year]
    for i in range(len(wanted.index)):
        n.storage_units.loc['Fixed ' + wanted.index[i], 'p_nom']-=wanted.loc[wanted.index[i],'p_nom']
        if n.storage_units.loc['Fixed ' + wanted.index[i], 'p_nom']<=0:
            n.storage_units.loc['Fixed ' + wanted.index[i], 'p_nom'] = 0

    #H2
    wanted=df_H[df_H.year_removed==year]
    
    n.links.loc[wanted.index,'p_nom']-=wanted.p_nom
    n.links.loc[n.links.p_nom<0,'p_nom']=0

    #H2_store
    wanted=df_S[df_S.year_removed==year]
    
    n.stores.loc[wanted.index,'e_nom']-=wanted.p_nom
    n.stores.loc[n.stores.e_nom<0,'e_nom']=0


def delete_original_RES(n,year,df,saved_potential,regional_potential):
    """  Reduces or removes the capacities of renewable energy source (RES) generators scheduled for removal in the specified year.

    This function adjusts the nominal capacities (p_nom) and maximum capacities (p_nom_max) of 'Fixed' RES generators in the network.
    It also updates the saved potential for each generator and ensures that the capacities do not exceed the regional potential.

    Parameters:
    -----------
    n : Network
        The network object containing the RES generators to be updated.
    year : int
        The year in which the capacity adjustments or removals are applied.
    df : pd.DataFrame
        A DataFrame tracking the RES generator capacities and their removal schedules.
    saved_potential : pd.Series
        A series tracking the remaining potential for each generator.
    regional_potential : float
        The regional potential limit for generator capacities.

    Returns:
    --------
    None
    """
    wanted=df[{'bus','p_nom'}][df.year_removed==year]
    for i in range(len(wanted.index)):
        
        n.generators.loc['Fixed ' + wanted.index[i], 'p_nom']-=wanted.loc[wanted.index[i],'p_nom']
        n.generators.loc['Fixed ' + wanted.index[i], 'p_nom_max']+=wanted.loc[wanted.index[i],'p_nom']
        saved_potential[wanted.index[i]]+=wanted.loc[wanted.index[i],'p_nom']
        # n.generators.loc[wanted.index[i], 'p_nom_max']+=wanted.loc[wanted.index[i],'p_nom']
        if n.generators.loc[wanted.index[i], 'p_nom_max'] + wanted.loc[wanted.index[i],'p_nom'] < regional_potential:
            n.generators.loc[wanted.index[i], 'p_nom_max']+=wanted.loc[wanted.index[i],'p_nom']
            
        if n.generators.loc['Fixed ' + wanted.index[i], 'p_nom']<=0:
            n.generators.loc['Fixed ' + wanted.index[i], 'p_nom'] = 0

def remove_phased_out (n):
    """
     Removes generators that have been phased out (i.e., those with zero nominal capacity).

    This function iterates through non-extendable generators in the network, and removes those whose 
    nominal capacity (p_nom) is zero, except those labeled as 'Fixed'.

    Parameters:
    -----------
    n : Network
        The network object containing the generators.

    Returns:
    --------
    None
    """

    for i in n.generators.index[n.generators.p_nom_extendable==False]:
        if 'Fixed ' not in i:
            if n.generators.p_nom[i] == 0:
                n.remove('Generator', i)