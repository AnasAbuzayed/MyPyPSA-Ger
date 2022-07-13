import os
import pandas as pd
from vresutils.costdata import annuity
import data

#print('enter network name')
network_name=data.network_name
name=network_name[:-3]

def createFolder(directory):
    try:
        if not os.path.exists(directory):
            os.makedirs(directory)
    except OSError:
        print ('Error: Creating directory. ' +  directory)    




def convert_opt_to_conv(n,year,res_add):
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
                if Value >=g.p_nom_max.item():
                    Value=g.p_nom_max.item()
                    
                n.add("Generator","Fixed " + idx[i],
                      bus=g.bus[0],p_nom=Value,p_nom_opt=0,marginal_cost=g.marginal_cost[0],
                      capital_cost=0, carrier=g.carrier[0],p_nom_extendable=False,
                      p_nom_max=p_max,control=g.control[0],
                      efficiency=g.efficiency[0], p_min_pu=0, p_max_pu=y2)
                
                n.generators.loc["Fixed " + idx[i],'weight']=g.weight[0]
        else:
            print('Conventional Extendable: This is executed for {}'.format(idx[i]))
            g=n.generators.loc[n.generators.index == idx[i]].copy()
            if idx[i] in c.index:
                Value=c.p_nom[idx[i]]
            else:
                Value=0

#            y1=y2*Value
            n.add("Generator","Fixed " + idx[i],
                  bus=g.bus[0],p_nom=Value,p_nom_opt=0,marginal_cost=g.marginal_cost[0],
                  capital_cost=0, carrier=g.carrier[0],p_nom_extendable=False,control='',
                  p_nom_max=g.p_nom_max[0],
                  efficiency=g.efficiency[0])
            
            n.generators.loc["Fixed " + idx[i],'weight']=g.weight[0]
    for i in n.generators.index:
        print('Setting p_nom_opt to zero for {}'.format(i))
        n.generators.loc[i,'p_nom_opt']=0
    
    
    # Biomass & ROR
    cap_bio= ((annuity(30, 0.07) +
                             3.6/100.) *
                             2350*1e3 * 1)
    cap_ror= ((annuity(80, 0.07) +
                             2/100.) *
                             2500*1e3 * 1)

    for idx in n.generators.index[(n.generators.carrier=='biomass') | (n.generators.carrier=='ror')]:
        print(idx)
        n.generators.loc[n.generators.index == idx,'capital_cost']= cap_bio if idx.split()[-1] == 'biomass' else cap_ror
        g=n.generators.loc[n.generators.index == idx].copy()
        n.add("Generator","Fixed " + idx,
              bus=g.bus[0],p_nom=g.p_nom[0],p_nom_opt=0,marginal_cost=g.marginal_cost[0],
              capital_cost=0, carrier=g.carrier[0],p_nom_extendable=False,
              p_nom_max=0,efficiency=g.efficiency[0])

        n.generators.loc[n.generators.index == idx,'p_nom_max']=0
        n.generators.loc[n.generators.index == idx,'p_nom_extendable']=True
        n.generators.loc[n.generators.index == idx,'p_nom']=0
        n.generators.loc[n.generators.index == idx,'p_nom_opt']=0

    return df


def create_fixed_lines(n):
    for i in n.lines.index:
        print(i)
        a=n.lines.loc[n.lines.index == str(i)]
        n.add("Line",name='Fixed {}'.format(i), bus0=a.bus0[0],bus1=a.bus1[0],s_max_pu=a.s_max_pu[0],
        s_nom=a.s_nom[0], length=a.length[0], capital_cost = 0, s_nom_extendable=False,s_nom_min=0)

        n.lines.loc[n.lines.index=='Fixed '+ str(i),'num_parallel']=a.num_parallel[0]
        n.lines.loc[n.lines.index=='Fixed '+ str(i),'v_nom']=a.v_nom[0]
        n.lines.loc[n.lines.index=='Fixed '+ str(i),'type']=a['type'][0]
        n.lines.loc[n.lines.index=='Fixed '+ str(i),'s_nom_min']=0
        n.lines.loc[n.lines.index==str(i),'num_parallel']=0
        n.lines.loc[n.lines.index==str(i),'x']=0
        n.lines.loc[n.lines.index==str(i),'r']=0
        n.lines.loc[n.lines.index==str(i),'b']=0
        n.lines.loc[n.lines.index==str(i),'s_nom_min']=0
        n.lines.loc[n.lines.index==str(i),'s_nom']=0
        n.lines.loc[n.lines.index==str(i),'s_nom_opt']=0
    for i in n.lines.index:
        if 'Fixed' not in i:
            print(i)
            n.lines.loc[i,'s_nom_extendable']=True
            n.lines.loc[i,'s_nom']=0            
        else:
            n.lines.loc[i,'carrier']='AC'

            
    for i in n.links.index:
        print(i)
        a=n.links.loc[n.links.index == str(i)]
        n.add("Link",name='Fixed {}'.format(i), bus0=a.bus0[0],bus1=a.bus1[0],carrier= a.carrier[0],
        length=a.length[0], p_nom_extendable=False, capital_cost = 0, p_nom=a.p_nom[0])
        n.links.loc[n.links.index==str(i),'p_nom_opt']=0
        n.links.loc[n.links.index==str(i),'p_nom']=0
        n.links.loc[n.links.index=='Fixed '+ str(i),'capital_cost_lc']=0
        n.links.loc[n.links.index=='Fixed '+ str(i),'capital_cost']=0
        n.links.loc[n.links.index=='Fixed '+ str(i),'carrier']='DC'
        n.links.loc[n.links.index=='Fixed '+ str(i),'geometry']=a.geometry[0]
        n.links.loc[n.links.index=='Fixed '+ str(i),'tags']=a.tags[0]
        n.links.loc[n.links.index=='Fixed '+ str(i),'p_min_pu']=a.p_min_pu[0]
        n.links.loc[n.links.index=='Fixed '+ str(i),'type']=a.type[0]
        n.links.loc[n.links.index=='Fixed '+ str(i),'efficiency']=a.efficiency[0]
        n.links.loc[n.links.index=='Fixed '+ str(i),'p_nom_min']=0
    for i in n.links.index:
        if 'Fixed' not in i:
            print(i)
            n.links.loc[i,'p_nom_extendable']=True


def initial_storage(n):    
    initial=n.storage_units.state_of_charge_initial.copy()
    last_state=n.storage_units_t.state_of_charge[n.storage_units_t.state_of_charge.index==n.storage_units_t.state_of_charge.index[-1]].copy()
    
    for i in last_state.columns:
        print(i)
        initial.loc[i]=last_state[i][0]

    n.storage_units.state_of_charge_initial=initial





