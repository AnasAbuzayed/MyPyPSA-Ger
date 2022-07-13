import requests
import os
import pandas as pd
import numpy as np
import math
import logging
logger = logging.getLogger(__name__)
from numpy import pi as pi
from numpy import sin as sin
from numpy import cos as cos 
from numpy import arccos as arccos

print('enter data network name')
network_name=  str(input())
name=network_name[:-3]

def Biomass_data (n,name):
    if os.path.exists('{}/bio_basic_removal.csv'.format(name)):
        remove=pd.read_csv('{}/bio_basic_removal.csv'.format(name),index_col=0)
    else:
        data=pd.read_csv('data/renewable_power_plants_DE_bio.csv')
        data=data[['commissioning_date','decommissioning_date','technology','electrical_capacity','lat','lon']]
        data.columns=['year_added','year_removed','carrier','p_nom','latitude','longitude']
        data.carrier=data.carrier.replace('Sewage and landfill gas', 'biomass')
        data.carrier=data.carrier.replace('Biomass and biogas', 'biomass')
        data.drop(data[data.carrier != 'biomass' ].index, inplace=True)
        data.index=range(len(data))
    
        year_added=[]
        year_removed=[]
        for i in range(len(data)):
            year_added.append( int(data[data.columns[0]][i][:4]) )
            year_removed.append( int(data[data.columns[0]][i][:4]) +30)
        
        data.year_added=year_added
        data.year_removed=year_removed
        
        data.drop(data[data.year_added < 1989 ].index, inplace=True)
        data.drop(data[data.year_added > 2020].index, inplace=True)
    
        data.drop(data[np.isnan(data.longitude) ==True].index, inplace=True)
        data.drop(data[np.isnan(data.latitude) ==True].index, inplace=True)
        data.drop(data[np.isnan(data.p_nom) ==True].index, inplace=True)
    
        data['bus']=data.latitude*0
        a=n.buses.loc[n.generators.bus[n.generators.carrier=='biomass'], ['x','y']] 
        a['bus']=a.index
        a.index=range(len(a))
        a.y*=pi/180
        a.x*=pi/180
        data.longitude*=pi/180
        data.latitude*=pi/180
        
        data.drop(data[np.isnan(data.longitude) ==True].index, inplace=True)
        data.drop(data[np.isnan(data.latitude) ==True].index, inplace=True)
        data.index=range(len(data))
        
        R=6371 # mean earth radius in km
        buses=[]
        #Great-Circle Distance Formula
        for j in range(len(data)):
            distances=[]
            print(j)
            wanted_buses=list(n.generators.bus[n.generators.carrier==data.carrier[j]])
            for i in range(len(a)):
                distances.append(arccos(sin(a.y[i]) * sin(data.latitude[j]) + cos(a.y[i]) *
                                        cos(data.latitude[j]) * cos(a.x[i] - data.longitude[j])) * R)
            df=pd.DataFrame({'bus':a.bus,'distance':distances})
            for i in range(len(df.bus)):
                if df.bus[i] not in wanted_buses:
                    df=df.drop([i],axis=0)
            df.index=range(len(df))
            buses.append(df.bus[np.where(df.distance==min(df.distance))[0][0]])
        
        data['bus']=buses
        data.index=range(len(data))
        ### Removal     
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
        remove.to_csv('{}/bio_basic_removal.csv'.format(name))
    
    correct=remove.groupby(['carrier','bus']).agg({'p_nom':['sum']})
    correct=correct.stack().reset_index()
    correct=correct[['carrier','p_nom','bus']]
    correct.index=correct.bus + ' ' + correct.carrier

    for i in correct.index:
        logger.info("Correcting {} capacity: {} MW instead of {} MW".format(i,
                                                                            round(correct.loc[i,'p_nom'],3),
                                                                            round(n.generators.loc[i,'p_nom'],3)))
        n.generators.loc[i,'p_nom']=correct.loc[i,'p_nom']


    addition=remove[['carrier','p_nom','bus']]
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
    add.to_csv('{}/biomass_basic_addition.csv'.format(name))


    return remove



def RES_data(n,name):
        
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
    
    R=6371 # mean earth radius in km
    buses=[]
    #Great-Circle Distance Formula
    for j in range(len(data)):
        distances=[]
        print(j)
        wanted_buses=list(n.generators.bus[n.generators.carrier==data.carrier[j]])
        for i in range(len(a)):
            distances.append(arccos(sin(a.y[i]) * sin(data.latitude[j]) + cos(a.y[i]) *
                                    cos(data.latitude[j]) * cos(a.x[i] - data.longitude[j])) * R)
        df=pd.DataFrame({'bus':a.bus,'distance':distances})
        for i in range(len(df.bus)):
            if df.bus[i] not in wanted_buses:
                df=df.drop([i],axis=0)
        df.index=range(len(df))
        buses.append(df.bus[np.where(df.distance==min(df.distance))[0][0]])
    
    data['bus']=buses
    data.index=range(len(data))
    
    
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


    
def Correct_coal(n,name):
    data = pd.read_csv('data/conventional_power_plants_DE.csv')
    data =data [['capacity_net_bnetza','energy_source','commissioned','retrofit','status','lat','lon']]
    data=data.rename(columns={"capacity_net_bnetza": "p_nom", "energy_source": "carrier"})
    data.drop(data[data.carrier !='Hard coal'].index, inplace=True)
    data.drop(data[data.status =='shutdown'].index, inplace=True)
    data.carrier=data.carrier.replace('Hard coal', 'coal')
    data.index=range(len(data))
    
    for i in range(len(data)):
        if data.retrofit[i] > data.commissioned[i]:
            print(i)
            data.commissioned[i]=data.commissioned[i] + 20

    data.drop(data[data.commissioned<1969].index, inplace=True)
    data['year_removed']=data.commissioned + 50

    data.index=range(len(data))
    
    data['bus']=data.lat*0
    a=n.buses.loc[n.generators.bus[n.generators.carrier=='coal'], ['x','y']] 
    a['bus']=a.index
    a.index=range(len(a))
    a.y*=pi/180
    a.x*=pi/180
    data.lon*=pi/180
    data.lat*=pi/180
    
    
    
    R=6371 # mean earth radius in km
    buses=[]
    #Great-Circle Distance Formula
    for j in range(len(data)):
        distances=[]
        for i in range(len(a)):
            distances.append(arccos(sin(a.y[i]) * sin(data.lat[j]) + cos(a.y[i]) *
                                    cos(data.lat[j]) * cos(a.x[i] - data.lon[j])) * R)
        df=pd.DataFrame({'bus':a.bus,'distance':distances})
        buses.append(df.bus[np.where(df.distance==min(df.distance))[0][0]])
    
    data['bus']=buses
    data=data[['carrier' ,'p_nom','bus','year_removed' ]]
    data.index=data.bus + ' ' + data.carrier



    correct=data.groupby(['carrier','bus']).agg({'p_nom':['sum']})
    correct=correct.stack().reset_index()
    correct=correct[['carrier','p_nom','bus']]
    correct.index=correct.bus + ' ' + correct.carrier

    for i in correct.index:
        logger.info("Correcting {} capacity: {} MW instead of {} MW".format(i,
                                                                            round(correct.loc[i,'p_nom'],3),
                                                                            round(n.generators.loc[i,'p_nom'],3)))
        n.generators.loc[i,'p_nom']=correct.loc[i,'p_nom']


    data=data[data.year_removed >=2020]
    data.to_csv('{}/coal_basic_removal.csv'.format(name))

    return data

def Base_Removal_Data(n):
    data = pd.read_csv('data/ppl.csv')
    df1 = data[data.carrier == 'hydro']
    df2 = data[data.carrier != 'hydro']
    df1.drop(df1[df1.technology !='Run-Of-River'].index, inplace=True)
    data= pd.concat([df1,df2])
    
    data=data[['carrier','p_nom','lat','lon','yeardecommissioning','yearcommissioned','retrofit']] ##'id', 'Country'
    
    #data['carrier']=data['carrier'].replace('waste','OCGT')
    #data['carrier']=data['carrier'].replace('other','OCGT')
    
    data.drop(data[data.carrier =='nuclear'].index, inplace=True)
    data.drop(data[data.carrier =='biomass'].index, inplace=True)
    data.drop(data[data.carrier =='other'].index, inplace=True)
    data.drop(data[data.carrier =='waste'].index, inplace=True)
    data.drop(data[data.carrier =='storage technologies'].index, inplace=True)
    data.carrier=data.carrier.replace('hydro','ror')
    df=pd.DataFrame({'p_nom':data.p_nom,'carrier':data.carrier})
    summation=df.groupby('carrier').sum()
    data.index=range(len(data))
    
    data['bus']=data.lat*0
    a=n.buses[['x','y']]
    a['bus']=a.index
    a.index=range(len(a))
    a.y*=pi/180
    a.x*=pi/180
    data.lon*=pi/180
    data.lat*=pi/180
    
    
    
    R=6371 # mean earth radius in km
    buses=[]
    #Great-Circle Distance Formula
    for j in range(len(data)):
        distances=[]
        for i in range(len(a)):
            distances.append(arccos(sin(a.y[i]) * sin(data.lat[j]) + cos(a.y[i]) *
                                    cos(data.lat[j]) * cos(a.x[i] - data.lon[j])) * R)
        df=pd.DataFrame({'bus':a.bus,'distance':distances})
        buses.append(df.bus[np.where(df.distance==min(df.distance))[0][0]])
    


    data['bus']=buses
    temp=data['yeardecommissioning']
    data=data[['carrier','p_nom','bus','yearcommissioned','retrofit']]
    data['year_removed']=temp
    data.drop(data[data.carrier =='coal'].index, inplace=True)

    data.drop(data[data.year_removed <=2020].index, inplace=True)

    ### Correcting CCGT & OCGT
    pre_CCGT=round(data.p_nom[data.carrier=='CCGT'].sum(),3)
    pre_OCGT=round(data.p_nom[data.carrier=='OCGT'].sum(),3)

    data.p_nom[data.carrier=='CCGT']=data.p_nom[data.carrier=='CCGT']*1.25921273 ## TODO: Maybe in a nicer way?
    data.p_nom[data.carrier=='OCGT']=data.p_nom[data.carrier=='OCGT']*1.25921273 ## TODO: Maybe in a nicer way?

    logger.info("Correcting CCGT capacity: {} MW instead of {} MW".format(round(data.p_nom[data.carrier=='CCGT'].sum(),3),pre_CCGT))
    logger.info("Correcting OCGT capacity: {} MW instead of {} MW".format(round(data.p_nom[data.carrier=='OCGT'].sum(),3),pre_OCGT))


    data.index=data.bus + ' ' + data.carrier

    data.to_csv('{}/conventional_basic_removal.csv'.format(name))
    return data


def resample_gen_profiles(n,net_name,resample_factor):
    gen_profiles=pd.read_csv('{}/gen_profiles.csv'.format(net_name),index_col=0,parse_dates=True)
    gen_profiles=gen_profiles.resample('{}H'.format(resample_factor)).mean()

    for i in n.generators.index[n.generators.carrier=='solar']:
        if (i not in gen_profiles.columns) | (math.isnan(gen_profiles[i][0])):
            continue
        else:
            data= pd.DataFrame ({'electricity':gen_profiles[i]})
            logger.info("Correcting {} generation profile: {} CF instead of {}".format(i,
                                                                        round(data.electricity.mean(),3),
                                                                        round(n.generators_t.p_max_pu[i].mean(),3)))

    for i in n.generators.index[n.generators.carrier=='onwind']:
        if (i not in gen_profiles.columns) | (math.isnan(gen_profiles[i][0])):
            continue
        else:
            data= pd.DataFrame ({'electricity':gen_profiles[i]})
            logger.info("Correcting {} generation profile: {} CF instead of {}".format(i,
                                                                        round(data.electricity.mean(),3),
                                                                        round(n.generators_t.p_max_pu[i].mean(),3)))


def update_rens_profiles(n,reference_year):
    
    token = '14028bca8d326e4108f800afb3be24fa012999ef'
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

    # Solar

    for i in n.generators.index[n.generators.carrier=='solar']:
        if (i not in gen_profiles.columns) | (math.isnan(gen_profiles[i][0])):
            lat=n.buses.loc[n.generators.loc[i,'bus'],'y']
            lon=n.buses.loc[n.generators.loc[i,'bus'],'x']

            url = api_base + 'data/pv'
            
            args = {
                'lat': lat,
                'lon': lon,
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
            
            r = s.get(url, params=args)
            parsed_response = json.loads(r.text)
            data = pd.read_json(json.dumps(parsed_response['data']), orient='index')
            time.sleep(15)

        else:
            data= pd.DataFrame ({'electricity':gen_profiles[i]})

        logger.info("Correcting {} generation profile: {} CF instead of {}".format(i,
                                                                    round(data.electricity.mean(),3),
                                                                    round(n.generators_t.p_max_pu[i].mean(),3)))
        gen_profiles[i]=n.generators_t.p_max_pu[i]
        gen_profiles.to_csv('{}/gen_profiles.csv'.format(name))

    #Onwind

    for i in n.generators.index[n.generators.carrier=='onwind']:
        if (i not in gen_profiles.columns) | (math.isnan(gen_profiles[i][0])):

            lat=n.buses.loc[n.generators.loc[i,'bus'],'y']
            lon=n.buses.loc[n.generators.loc[i,'bus'],'x']
    
        
            url = api_base + 'data/wind'
        
            args = {
                'lat': lat,
                'lon': lon,
                'date_from': str(reference_year)+'-01-01',
                'date_to': str(reference_year)+'-12-31',
                'capacity': 1.0,
                'height': 101.5, # min:84, max:119, avg:101.5
                'turbine': 'Vestas V112 3000',
                'format': 'json'
            }
            
            r = s.get(url, params=args)
            
            parsed_response = json.loads(r.text)
            data = pd.read_json(json.dumps(parsed_response['data']), orient='index')
            time.sleep(15)

        else:
            data= pd.DataFrame ({'electricity':gen_profiles[i]})

        logger.info("Correcting {} generation profile: {} CF instead of {}".format(i,
                                                                    round(data.electricity.mean(),3),
                                                                    round(n.generators_t.p_max_pu[i].mean(),3)))

        gen_profiles[i]=n.generators_t.p_max_pu[i]
        gen_profiles.to_csv('{}/gen_profiles.csv'.format(name))
    

        # n.generators_t.p_max_pu[i]= list(data.
        #                          electricity) if len(n.snapshots) > 365 else list(data.electricity
        #                                                                           .resample('{}H'.format(resample_factor)).mean())





