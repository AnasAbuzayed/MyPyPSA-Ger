# -*- coding: utf-8 -*-
"""
Created on Sun May  10 02:18:04 2020

@author: anasi
          name      color
0         CCGT        red
1         OCGT     salmon
2      biomass  darkgreen
3         coal     sienna
4      lignite       gray
5      nuclear    fuchsia
6   offwind-ac     indigo
7   offwind-dc       blue
8          oil          k
9       onwind     violet
10         ror       cyan
11       solar     orange
"""
import pandas as pd
import pypsa
import data
network_name=data.network_name

print('enter regional potential value')
regional_potential=int(input())

def update_load(n,factor):
    for i in range(len(n.loads_t.p_set.columns)):
        n.loads_t.p_set[n.loads_t.p_set.columns[i]]*=factor

def update_cost(n,year,cost_factors,fuel_cost):
    
    #Generators
    for tech in cost_factors.columns:
        n.generators.capital_cost[n.generators.carrier==tech]*= cost_factors[tech].loc[year]
        n.generators.marginal_cost[n.generators.carrier==tech]*= cost_factors[tech].loc[year]
        n.storage_units.capital_cost[n.storage_units.carrier==tech]*= cost_factors[tech].loc[year]
        n.storage_units.marginal_cost[n.storage_units.carrier==tech]*= cost_factors[tech].loc[year]

#    n.generators.marginal_cost= n.generators.marginal_cost*0.99 ## TODO: Decrease only RES, seperate for carriers
    # Fuel
    # years = [int(item) for item in fuel_cost.columns]

    # for z in range(len(years[:-1])):
    #     if years[z] <= year < years[z+1]:
    #         spec_year=years[z]
    # if year == 2050:
    #     spec_year=years[z]
    
    fuels=list(fuel_cost.columns)

    for tech in fuels:
            print('correcting {} marginal cost at {}'.format(tech,year))
            eff=n.generators.efficiency[n.generators.carrier==tech].unique().item()
            old_cost=fuel_cost.loc[year-1,tech]/eff
            new_cost=fuel_cost.loc[year,tech]/eff
            n.generators.marginal_cost[n.generators.carrier==tech]+= new_cost-old_cost

def update_co2price(n,year):
    dif= co2price.loc[year].item() - co2price.loc[year-1].item()
    for carrier in list(n.carriers.index[n.carriers.co2_emissions >0]):
        for gen in list(n.generators.index[n.generators.carrier==carrier]):
            print(gen)
            val=dif* n.carriers.loc[carrier].co2_emissions / n.generators.loc[gen,'efficiency']
            n.generators.loc[gen,'marginal_cost']+=val

def update_co2limit(n, new_lim):
    """
    

    Parameters
    ----------
    n : TYPE
        the network.
    new_lim : TYPE
        new co2 limit.

    Update a CO2 constraint on a yearly basis
    """
    n.global_constraints.constant=float(new_lim)

def delete_old_gens(n,year,base):    
    wanted=base[{'bus','p_nom'}][base.year_removed==year].sum(axis=1)
    for i in range(len(wanted.index)):
        if wanted.index[i] in n.generators.index:
            if wanted.index[i].split()[-1] in ['biomass','ror']:
                print(i)
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



def Phase_out(n,carrier, phase_year):
    a=n.generators[n.generators.carrier==carrier]
    Total=a.p_nom.sum()
    Yearly = Total / (phase_year - 2020)
    dist = []
    for i in a.index:
        dist.append( Yearly* a.p_nom.loc[i] / Total)
    return a, Yearly


def remove_Phase_out (n,removal, yearly_value):
    for i in removal.index:
        remove=yearly_value* removal.p_nom.loc[i] / removal.p_nom.sum()
        val= n.generators.loc[i, 'p_nom'] - remove
        if val >= 1 :
            n.generators.loc[[i], 'p_nom']= val
        else:
            n.generators.loc[[i], 'p_nom'] = 0


def update_const_gens(n):
    for i in range(len(n.generators.index)):
        if n.generators.index[i][:5] =='Fixed':
            print(i)
            n.generators.p_nom[i]+=n.generators.p_nom_opt[n.generators.index[i][6:]]
            n.generators.p_nom_opt[i]=n.generators.p_nom[i]
            if n.generators.index[i].split()[-1] not in ['CCGT', 'OCGT']:
                n.generators.p_nom_max[n.generators.index[i]]-=n.generators.p_nom_opt[n.generators.index[i][6:]]
                n.generators.p_nom_max[n.generators.index[i][6:]]-=n.generators.p_nom_opt[n.generators.index[i][6:]]
                if n.generators.p_nom_max[n.generators.index[i][6:]] < 0:
                    n.generators.loc[n.generators.index == n.generators.index[i][6:], 'p_nom_max']=0
    return


def update_const_lines(n):
    for i in n.lines.index:
        if 'Fixed' in i:
            print(i)
            n.lines.loc[i,'s_nom']+=n.lines.loc[i.split()[1],'s_nom']
            n.lines.loc[i,'s_nom_opt']=n.lines.loc[i,'s_nom']
            n.lines.loc[i,'num_parallel']+=n.lines.loc[i.split()[1],'num_parallel']
            n.lines.loc[i.split()[1],'num_parallel']=0
            n.lines.loc[i.split()[1],'s_nom']=0
            n.lines.loc[i.split()[1],'s_nom_opt']=0
            n.lines.loc[i.split()[1],'x']=0
            n.lines.loc[i.split()[1],'r']=0
            n.lines.loc[i.split()[1],'b']=0


    for i in n.links.index:
        if 'Fixed' in i:
            n.links.loc[i,'p_nom']+=n.links.loc[i.split()[1],'p_nom']


def Yearly_potential(n,saved_potential,regional_potential):
    for i in n.generators.index[n.generators.p_nom_extendable==True]:
        print(i)
        if i.split()[-1] not in ['biomass','ror']:
            print(i)
            saved_potential[i]-=n.generators.p_nom_opt[i]
            if saved_potential[i] >= regional_potential:
                n.generators.loc[i,'p_nom_max']=regional_potential
            else:
                n.generators.loc[i,'p_nom_max']=saved_potential[i]
    for i in saved_potential.index:
        if saved_potential[i] <= 1:
            n.generators.loc[i,'p_nom_max']=0
            saved_potential[i]=0
    return saved_potential
    
def append_gens(n,year,df):
    idx=[]
    bus=[]
    opt_p=[]
    life=[]
    lifetime=pd.DataFrame({'carrier':['CCGT','OCGT','offwind-ac',
                                    'offwind-dc','onwind','solar'],
                         'life':[30,30,25,25,25,25]})
    for i in n.generators[n.generators.p_nom_extendable==True].index:
        if i.split()[-1] not in ['biomass','ror']:
            print(i)
            idx.append(i)
            bus.append(n.generators.loc[i,'bus'])
            opt_p.append(n.generators.loc[i,'p_nom_opt'])
            life.append(year + lifetime.loc[lifetime.carrier==idx[-1].split()[-1], 'life'].item())
    temp=pd.DataFrame({'bus':bus,'p_nom':opt_p,'year_added':[year]*len(opt_p),'year_removed':life})
    temp.index=idx
    df = pd.concat([df, temp], ignore_index=False)
    return df


def delete_gens(n,year,df,saved_potential):
    wanted=df[{'bus','p_nom'}][df.year_removed==year]
    for i in range(len(wanted.index)):
        print(i)
        n.generators.loc['Fixed ' + wanted.index[i], 'p_nom']-=wanted.loc[wanted.index[i],'p_nom']
        n.generators.loc['Fixed ' + wanted.index[i], 'p_nom_max']+=wanted.loc[wanted.index[i],'p_nom']
        saved_potential[wanted.index[i]]+=wanted.loc[wanted.index[i],'p_nom']
        if n.generators.loc[wanted.index[i], 'p_nom_max'] + wanted.loc[wanted.index[i],'p_nom'] < regional_potential:
            n.generators.loc[wanted.index[i], 'p_nom_max']+=wanted.loc[wanted.index[i],'p_nom']

        if n.generators.loc['Fixed ' + wanted.index[i], 'p_nom']<=0:
            n.generators.loc['Fixed ' + wanted.index[i], 'p_nom'] = 0


def delete_original_RES(n,year,df,saved_potential):
    wanted=df[{'bus','p_nom'}][df.year_removed==year]
    for i in range(len(wanted.index)):
        print(i)
        n.generators.loc['Fixed ' + wanted.index[i], 'p_nom']-=wanted.loc[wanted.index[i],'p_nom']
        n.generators.loc['Fixed ' + wanted.index[i], 'p_nom_max']+=wanted.loc[wanted.index[i],'p_nom']
        saved_potential[wanted.index[i]]+=wanted.loc[wanted.index[i],'p_nom']
        # n.generators.loc[wanted.index[i], 'p_nom_max']+=wanted.loc[wanted.index[i],'p_nom']
        if n.generators.loc[wanted.index[i], 'p_nom_max'] + wanted.loc[wanted.index[i],'p_nom'] < regional_potential:
            n.generators.loc[wanted.index[i], 'p_nom_max']+=wanted.loc[wanted.index[i],'p_nom']
            
        if n.generators.loc['Fixed ' + wanted.index[i], 'p_nom']<=0:
            n.generators.loc['Fixed ' + wanted.index[i], 'p_nom'] = 0


 
def remove_phased_out (n):
    for i in n.generators.index[n.generators.p_nom_extendable==False]:
        if 'Fixed ' not in i:
            print(i)
            if n.generators.p_nom[i] == 0:
                n.remove('Generator', i)

  



