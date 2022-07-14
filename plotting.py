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
import matplotlib.pyplot as plt
import yaml
#import requests
import json
import pypsa
import matplotlib as mpl
import cartopy.crs as ccrs
from matplotlib.offsetbox import AnchoredText
import re
import data
from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper, FullLoader

with open(r'config.yaml') as file:
    # The FullLoader parameter handles the conversion from YAML
    # scalar values to Python the dictionary format
    config= yaml.load(file, Loader=yaml.FullLoader)
    
network_name=data.network_name

name=network_name[:-3]

def colors_map(data):
    df=pd.DataFrame({'carrier':['CCGT','OCGT','biomass','coal','lignite','nuclear','offwind-ac',
                                    'offwind-dc','oil','onwind','ror','solar','load'],
                         'color':['#b20101','#d35050','#0c6013','#707070','#9e5a01','#ff9000','#6895dd','#74c6f2',
                                  '#262626','#235ebc','#4adbc8','#f9d002','k']})

#'color':['red','salmon','darkgreen','sienna','gray','fuchsia','indigo','blue',
#                              'k','violet','cyan','orange']
    c=[]
    for i in range(len(data)):
        c.append(list(df.color[df.carrier==data.index[i]])[0])
    return c

def pie_exp(data):
    df=pd.DataFrame({'carrier':['CCGT','OCGT','biomass','coal','lignite','nuclear','offwind-ac',
                                    'offwind-dc','oil','onwind','ror','solar'],
                         'exp':[0,0,0,0,0,0,0.1,0.1,0,0.1,0.1,0.1]})
    d=[]
    for i in range(len(data)):
        d.append(list(df.exp[df.carrier==data.index[i]])[0])
    return d

def pie_chart(n,year):
    p_by_carrier = pd.DataFrame(index=n.generators_t.p[n.generators.index [n.generators.carrier!='load']].columns, columns=['p_by_carrier'])
    p_by_carrier.p_by_carrier= n.generators_t.p.sum()
    p_by_carrier.p_by_carrier*=int(8760/len(n.snapshots))

    val=[]
    typ=[]
    for i in range(len(p_by_carrier)):
        val.append(p_by_carrier.p_by_carrier[i])
        typ.append(re.split('\s+', p_by_carrier.index[i])[len(re.split('\s+', p_by_carrier.index[i]))-1])
    nnam=list(dict.fromkeys(typ))
    new_gen= []
    
    for i in range(len(nnam)): #TODO Automize colors 
        x=0
        for j in range(len(val)):
            if typ[j]==nnam[i]:
                x=x+val[j]
        new_gen.append(x)

    new_gen=pd.DataFrame(new_gen, columns=['gens'],index=nnam)
    
    colors = colors_map(new_gen)
    explode = pie_exp(new_gen)
    perc=(new_gen.loc['solar']+new_gen.loc['onwind']+new_gen.loc['offwind-ac']+
          new_gen.loc['offwind-dc']+new_gen.loc['ror'])/new_gen.sum()
    
    fig=plt.figure(figsize=(40, 10))
    plt.title('Generation shares year {} \n Renewables={}%'.format(year,round(perc*100,3)[0]),fontsize=20)
    patches, texts,junk = plt.pie(list(new_gen.gens),explode=explode, colors=colors,
                             autopct='%1.1f%%', shadow=True, startangle=140)
    plt.legend(patches, new_gen.index, loc="best")
    plt.savefig('{}/All Generation year {}'.format(name,year), pi=1600, bbox_inches='tight')
  #  plt.show()
    

    return round(perc*100,3)[0]


def installed_capacities(n,year):
    df=pd.DataFrame({'p_nom':n.generators.p_nom[n.generators.carrier!='load'],'carrier':n.generators.carrier[n.generators.carrier!='load']})
    summation=df.groupby('carrier').sum()
    shares=int(summation.loc['solar']+summation.loc['onwind']+
               summation.loc['offwind-ac']+summation.loc['offwind-dc']+summation.loc['ror'])/sum(summation.p_nom)
    
    colors = colors_map(summation)
    explode = pie_exp(summation)
    fig=plt.figure(figsize=(40, 10))
    plt.title('Installed Capacity year {}\n Total= {} GW, Renewables={} %'.format(year,
              round(sum(summation.p_nom)/1000,3), round(shares*100,3)),fontsize=20)
    patches, texts,junk = plt.pie(list(summation.p_nom),explode=explode, colors=colors,
                             autopct='%1.1f%%', shadow=True, startangle=140,textprops={'color':"w"})
    plt.legend(patches, summation.index, loc="best")
    plt.savefig('{}/Installation Shares year {}'.format(name,year), pi=1600, bbox_inches='tight')
   # plt.show()
    
    return round(shares*100,3)


def Gen_Bar(n,bar,year):
    p_by_carrier = n.generators_t.p.sum()
    val=[]
    typ=[]
    for i in range(len(p_by_carrier)):
        val.append(p_by_carrier[i])
        typ.append(re.split('\s+', p_by_carrier.index[i])[len(re.split('\s+', p_by_carrier.index[i]))-1])
    nnam=list(dict.fromkeys(typ))
    new_gen= []
    
    for i in range(len(nnam)):
        x=0
        for j in range(len(val)):
            if typ[j]==nnam[i]:
                x=x+val[j]
        new_gen.append(x)
    
    new_gen=pd.DataFrame(new_gen, index=nnam)
    for p in range(len(new_gen.index)):
        bar.loc[year,new_gen.index[p]]=new_gen.loc[new_gen.index[p]][0]/10**6

    return bar
    
def Inst_Bar(n,bar,year):
    
    df=pd.DataFrame({'p_nom':n.generators.p_nom[n.generators.carrier!='load'],'carrier':n.generators.carrier[n.generators.carrier!='load']})
    summation=df.groupby('carrier').sum()
    
    for p in range(len(summation.index)):
        bar.loc[year,summation.index[p]]=summation.loc[summation.index[p]][0]/10**3

    bar=bar.sort_index(axis=0,ascending=True)

    return bar

def Bar_to_PNG(n,bar,name,bar_type):
    
#    bar=bar.sort_index(axis=0,ascending=True)
    
    cols = list(bar.columns.values) 
    cols.pop(cols.index('solar')) 
    cols.pop(cols.index('offwind-dc'))
    cols.pop(cols.index('offwind-ac'))
    cols.pop(cols.index('onwind'))
    cols.pop(cols.index('ror'))
    cols.pop(cols.index('oil'))
    cols.pop(cols.index('coal'))
    cols.pop(cols.index('lignite'))

    if bar_type =='Generation':
        unit='TWh'
        bar*=int(8760/len(n.snapshots))
        bar= bar[ ['lignite','coal', 'oil'] + cols + ['ror','offwind-ac','offwind-dc','onwind','solar']] ##TODO: Check
        colors = colors_map(pd.DataFrame(index=bar.columns))

    if bar_type =='Installation':
        unit='GW'
        bar= bar [ ['lignite','coal', 'oil'] + cols + ['ror','offwind-ac','offwind-dc','onwind','solar']]
        colors = colors_map(pd.DataFrame(index=bar.columns))

    if 'load' in list(bar.columns):
        bar.drop('load',axis=1,inplace=True)

    
    ax = bar.plot(figsize=(40, 10),kind='bar', stacked=True,color=colors,fontsize=15)
    ax.set_xlabel("Years",fontsize=15)
    ax.set_ylabel("{} [{}]".format(bar_type,unit),fontsize=15)
    ax.grid()
    ax.set_title('{} shares {}'.format(bar_type,name),fontsize=30)
    plt.savefig('{}/{} Bar Plot {}'.format(name,bar_type,name), pi=1600, bbox_inches='tight')
    bar.to_csv('{}/{}_Bar.csv'.format(name,bar_type))

    

def Country_Map(n,year):
    opts = config['plotting']
    map_figsize = [10,10]#opts['map']['figsize']
    map_boundaries = opts['map']['boundaries']
    to_rgba = mpl.colors.colorConverter.to_rgba

    line_colors = {'cur': "purple",
                   'exp': mpl.colors.rgb2hex(to_rgba("red", 0.7), True)}
    tech_colors = opts['tech_colors']
    bus_sizes = (n.generators.query('carrier != "load"').groupby(['bus', 'carrier']).p_nom.sum())
    line_widths_exp =  n.lines.s_nom_opt[n.lines.s_nom_extendable==False]

    attribute='p_nom'
    linewidth_factor = opts['map'][attribute]['linewidth_factor']
    bus_size_factor  = opts['map'][attribute]['bus_size_factor']
    
    bus=[]
    car=[]
    for i in bus_sizes.index:
        bus.append(i[0])
        car.append(i[1])
    txt=pd.DataFrame({'Bus':bus,'Carrier':car,'P':bus_sizes})
    txt.index=range(len(bus))
    
    summation=txt.groupby('Bus').sum()
    shares=txt.groupby('Carrier').sum()
    res=(shares.P['solar']+shares.P['offwind-ac']+shares.P['offwind-dc']+shares.P['onwind']+shares.P['ror'])/shares.sum()[0]
    

    map_boundaries=[5,15,46,55]
    n_plo=n.copy()
    for lin in list(n_plo.lines.index[n_plo.lines.s_nom_extendable==True]):        
        n_plo.remove('Line', lin)
    
    fig, ax = plt.subplots(figsize=map_figsize, subplot_kw={"projection": ccrs.PlateCarree()})
    n_plo.plot(line_widths=line_widths_exp/linewidth_factor,
               title='Installation Distribution, RES = {}%'.format(round(res*100,3)),
               line_colors=pd.Series(line_colors['exp'], n_plo.lines.index),
               bus_sizes=bus_sizes/(2.5*bus_size_factor),
               bus_colors=tech_colors,
               boundaries=map_boundaries,
               geomap=True,color_geomap=True,
               ax=ax)
    ax.add_artist(AnchoredText("{}".format(year), loc=2))
#    for i in range(len(shares.index)):
#        print(colors_map(shares)[i])
#        ax.add_artist(AnchoredText("{}/n".format(shares.index[i]), loc=3,prop={'color':  colors_map(shares)[i]} ))
    ax.set_aspect('equal')
    ax.axis('off')
    plt.savefig('{}/Installation Map {}'.format(name,year), pi=1600, bbox_inches='tight')
#    plt.show()


    #### Load
    
    
    
    
    fig,ax = plt.subplots(1,1,subplot_kw={"projection":ccrs.PlateCarree()})
    fig.set_size_inches(6,6)
    load_distribution = n.loads_t.p_set.mean()
    n.plot(boundaries=map_boundaries,
           geomap=True,color_geomap=True,
           bus_sizes=load_distribution/bus_size_factor,
           ax=ax,title="Average Load distribution")
    ax.add_artist(AnchoredText("{}".format(year), loc=2))
    plt.savefig('{}/Average Load distribution {}'.format(name,year), pi=1600, bbox_inches='tight')
  #  plt.show()



