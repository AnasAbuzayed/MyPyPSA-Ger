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

import time
import sys
sys.path.insert(0, "./pypsa-eur/scripts/")
import os
import pypsa
import pandas as pd
import numpy as np
from prepare_network import set_line_s_max_pu, add_emission_prices
from vresutils.costdata import annuity
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import matplotlib as mpl
from matplotlib.offsetbox import AnchoredText
import yaml
#import requests
import json
from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper, FullLoader

from _helpers import configure_logging
import logging
logger = logging.getLogger(__name__)

from solve_network import (solve_network, prepare_network)
import re
import glob
from numpy import sin as sin
from numpy import cos as cos 
from numpy import arccos as arccos
from numpy import pi as pi
from pypsa.linopf import network_lopf
import math
import data #network_name
import plotting
import base
import Myopic #regional_potential



"""
Start the Myopic Process
"""



with open(r'pypsa-eur/config.yaml') as file:
    # The FullLoader parameter handles the conversion from YAML
    # scalar values to Python the dictionary format
    config= yaml.load(file, Loader=yaml.FullLoader)


tmpdir = config['solving'].get('tmpdir')
opts = config['scenario']['opts'][0].split('-')
solve_opts = config['solving']['options']


# Create a base network with a very high CO2 Limit, so that no renewables will be invested in
# and a CO2 Emission Price of the year 2019 == 25 Euro

#print('enter network name')
network_name=data.network_name
regional_potential=Myopic.regional_potential
#scenario_name
name=network_name[:-3]
base.createFolder(network_name[:-3])


n = pypsa.Network('pypsa-eur/results/networks/'+network_name)
data.update_rens_profiles(n,2013)
resample_factor=int(8760/len(n.snapshots))

data.resample_gen_profiles(n,net_name=network_name.replace('{}H'.format(resample_factor),'1H')[:-3],
                      resample_factor=resample_factor)


saved_potential=n.generators.p_nom_max[n.generators.p_nom_extendable==True]
phase_out_removal,yearly_phase_out=Myopic.Phase_out(n,'coal',2036)
phase_out_removal_lignite,yearly_phase_out_lignite=Myopic.Phase_out(n,'lignite',2036)
n.storage_units.p_nom_extendable=False ##To dobule check


co2lims = pd.read_csv('data/co2limits.csv') ##co2lims = pd.read_csv('co2limits.csv')
cost_factors= pd.read_csv('data/Cost_Factor.csv', index_col=0, header=0)
fuel_cost= pd.read_csv('data/fuel_cost.csv', index_col=0, header=0)
co2price = pd.read_csv('data/co2_price.csv', index_col=0)

"""
Logger
"""

agg_p_nom_minmax = pd.read_csv(config['electricity'].get('agg_p_nom_limits'),
                                       index_col=1)

var=['regional potential']
var.extend(list(agg_p_nom_minmax.index))
val=[regional_potential]
val.extend(list(agg_p_nom_minmax['max']))
txt=pd.DataFrame({'val':val}, index=var)
txt.to_excel("{}/Scenario_settings.xlsx".format(network_name[:-3]), index = True)
""""""


def read_data(n,name):
    if os.path.exists('{}/conventional_basic_removal.csv'.format(name)):
        conventional_base=pd.read_csv('{}/conventional_basic_removal.csv'.format(name),index_col=0)
    else:
        conventional_base=data.Base_Removal_Data(n)

    if os.path.exists('{}/res_basic_removal.csv'.format(name)):
        RES_base_remove=pd.read_csv('{}/res_basic_removal.csv'.format(name),index_col=0)
    else:
        _,RES_base_remove=data.RES_data(n,name)

    if os.path.exists('{}/res_basic_addition.csv'.format(name)):
        RES_base_addition=pd.read_csv('{}/res_basic_addition.csv'.format(name),index_col=0)
    else:
        RES_base_addition,_=data.RES_data(n,name)
    
    return conventional_base, RES_base_remove, RES_base_addition



Bio_data=data.Biomass_data(n,name)
conventional_base, RES_base_remove, RES_base_addition =read_data(n,network_name[:-3])
coal_data=data.Correct_coal(n,network_name[:-3])

conventional_base=conventional_base.append(coal_data, ignore_index=False)
conventional_base=conventional_base.append(Bio_data, ignore_index=False)

removal_data = conventional_base.append(RES_base_remove, ignore_index=False)
removal_data.to_csv('{}/All_removal_data.csv'.format(network_name[:-3]))
renewables=removal_data[removal_data.carrier=='ror']
renewables = renewables.append([removal_data[removal_data.carrier=='solar'],
                                removal_data[removal_data.carrier=='onwind'],
                                removal_data[removal_data.carrier=='offwind-dc'],
                                removal_data[removal_data.carrier=='offwind-ac'],], ignore_index=False)
renewables.drop(renewables[renewables.carrier == 'ror'].index, inplace=True)

df=base.convert_opt_to_conv(n,2020,RES_base_addition)



Myopic.update_load(n,1.1719335435638228)

base.create_fixed_lines(n)


set_line_s_max_pu(n)
Myopic.update_co2limit(n,int(co2lims.co2limit[co2lims.year==2020]))



obj=[]
ren_perc=[]


n.storage_units.state_of_charge_initial=0

n = prepare_network(n, solve_opts)
gen_bar= pd.DataFrame(index =list(range(2020,2051)),columns=list(n.generators.carrier.unique()))
inst_bar= pd.DataFrame(index = list(range(2020,2051)) , columns=list(n.generators.carrier[n.generators.carrier!='load'].unique()))

if os.path.exists('{}/test_back.nc'.format(name)):
    n = pypsa.Network('{}/test_back.nc'.format(name))
else:
    n.lopf(solver_name='gurobi')#, pyomo=False, formulation='kirchhoff')
    n.export_to_netcdf('{}/test_back.nc'.format(name))

n = solve_network(n, config=config, solver_dir=tmpdir,opts=opts)
saved_potential=Myopic.Yearly_potential(n,saved_potential,regional_potential) ##TODO CHECK saved_potential=n.generators.p_nom_max[n.generators.p_nom_extendable==True]

base.initial_storage(n)

n.generators.sign[n.generators.carrier=='load']=1


years_cols=list(range(2021,2051))
Potentials_over_years=pd.DataFrame({'2020':saved_potential})
Potentials_over_years=Potentials_over_years.reindex(columns=Potentials_over_years.columns.tolist() + years_cols)


obj.append(n.objective)

for i in range(2021,2051):#2051:
    print(i)
    Myopic.remove_Phase_out (n,phase_out_removal, yearly_phase_out)
    Myopic.remove_Phase_out (n,phase_out_removal_lignite, yearly_phase_out_lignite)
    if i == 2036:
        n.generators.p_nom[n.generators.carrier=='coal']=0
        n.generators.p_nom[n.generators.carrier=='lignite']=0
    Myopic.update_const_lines(n)
    Myopic.update_const_gens(n)
    plotting.installed_capacities(n,year=i-1)
    plotting.Country_Map(n,year=i-1)
    ren_perc.append(plotting.pie_chart(n,i-1))

    gen_bar=plotting.Gen_Bar(n,gen_bar,i-1)
    inst_bar=plotting.Inst_Bar(n,inst_bar,i-1)
    n.export_to_netcdf('{}/{}.nc'.format(name,i-1))
    # n=pypsa.Network('{}/{}.nc'.format(name,i-1))
    Myopic.update_cost(n,i,cost_factors,fuel_cost=fuel_cost)
    Myopic.update_load(n,1.01)
    Myopic.delete_gens(n,i,df,saved_potential)
    Myopic.delete_original_RES(n,i,renewables,saved_potential)
    Myopic.delete_old_gens(n,i,conventional_base)
    
    set_line_s_max_pu(n)
    Myopic.update_co2limit(n,int(co2lims.co2limit[co2lims.year==i]))
    # Myopic.update_co2price(n,year=i)
    n = prepare_network(n, solve_opts)
    n = solve_network(n, config=config, solver_dir=tmpdir,opts=opts)
    base.initial_storage(n)
    saved_potential=Myopic.Yearly_potential(n,saved_potential,regional_potential)
    Potentials_over_years.loc[:,i]=saved_potential
    df=Myopic.append_gens(n,i,df)
    obj.append(n.objective)



Myopic.update_const_lines(n)
Myopic.update_const_gens(n)
plotting.installed_capacities(n,year=i)
ren_perc.append(plotting.pie_chart(n,i))

gen_bar=plotting.Gen_Bar(n,gen_bar,i)
inst_bar=plotting.Inst_Bar(n,inst_bar,i)
plotting.Country_Map(n,year=i)

plotting.Bar_to_PNG(n,gen_bar,name,'Generation')
plotting.Bar_to_PNG(n,inst_bar,name,'Installation')
n.export_to_netcdf('{}/{}.nc'.format(name,i))
df.to_excel("{}/addition.xlsx".format(name), index = True)

objective=pd.DataFrame({'year':list(range(2020,2051)) , 'objective':obj,'RES_mix':ren_perc})
objective.to_excel("{}/objective.xlsx".format(name), index = False)
Potentials_over_years.to_excel("{}/Potentials_over_years.xlsx".format(name), index = True)
