# -*- coding: utf-8 -*-
"""
© Anas Abuzayed 2025

This script runs the full myopic modeling process for a PyPSA-based power system model:
    The Model description is published here: https://doi.org/10.1016/j.apenergy.2022.118576
    
    
Process:
    1) It reads user inputs (clusters, regional potential).
    2) Loads the configuration YAML (common settings).
    3) Loads a PyPSA network from the "Networks" folder*
    4) Processes data (if needed), then sets up the baseline scenario**
    5) Iterates year by year, applying expansions, retirements, re-optimizations.
    6) Logs and saves the final results (objective values, capacity additions, etc.) and plots.

*: Currently, the model allows for networks representing NUTS specs of Germany
**: Pre-processed are stored in Networks folder
You should have:
 - config.yaml specifiyng some scenario settings
 - a "Networks" folder containing network files,
 - a "Data" folder containintg scenario csv files 
 such as fuel/Capital costs, yearly expansion potential, 
 co2 emissions price and limit, etc...
"""

import os
import logging
import pandas as pd
import yaml
import pypsa
import warnings

import Model_Code.data_processing as dp
import Model_Code.base_functions as bf
import Model_Code.Myopic as mp
import Model_Code.plotting as pt
import Model_Code.H2_Ready as H2R

from Model_Code.Constraints import extra_functionality
warnings.filterwarnings("ignore")

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def main():
    """
    Executes the myopic optimization from user input to final output files.
    """

    # Read config.yaml
    with open(r'config.yaml', "r") as file:
        config = yaml.load(file, Loader=yaml.FullLoader)

    opts = config['scenario_settings']['opts'][0].split('-')
    solver_options = config['solving']['solver'].copy()
    tmpdir = config['solving'].get('tmpdir')
    colors=config['plotting']['tech_colors']

    #extract scenario settings
    scenario_settings = config.get("scenario_settings", {})
    print('enter clusters')
    clusters = int(input())    # default to 4 if not alligned with NUTS
    clusters = clusters if clusters in [4,13,37,194] else \
        scenario_settings.get("clusters")
    regional_potential = scenario_settings.get("regional_potential")[clusters]
    #demand_growth = scenario_settings.get("demand_growth", 1.0)
    # Possibly more, e.g. co2_price or co2_limit,demand_growth (still not implemented)
    logger.info("Using config-based scenario settings:")
    logger.info(f" clusters={clusters}, regional_potential={regional_potential}")

    # Construct a network path from the "Networks" folder
    #    Example file: "Networks/elec_s_3_ec_lcopt_Co2L-1H-Ep-CCL.nc" if clusters=3
    network_filename = f"Networks/elec_s_{clusters}_ec_lcopt_Co2L-1H-Ep-CCL.nc"
    if not os.path.exists(network_filename):
        raise FileNotFoundError(f"Cannot find network file: {network_filename}")

    # Load the PyPSA Network
    n = pypsa.Network(network_filename)
    n.generators["p_nom_min"] = 0

    # Create results folder(s)
    # For example, strip the ".nc" from network file for one folder,
    # and also create a folder named after the number of buses:
    name = network_filename[:-3]  # e.g. "Networks/elec_s_3_ec_lcopt_Co2L-1H-Ep-CCL"
    bf.createFolder(name)

    bus_folder = 'Results/'+str(int(len(n.buses)))
    bf.createFolder(bus_folder)

    # Update renewable profiles, availability, etc.
    dp.update_rens_profiles(n, reference_year=2013, name=name)
    bf.update_availability_profiles(n, name)


    # Read input data / CSVs from inside the
    co2lims = pd.read_csv(os.path.join("data", "co2limits.csv"))
    cost_factors = pd.read_csv(os.path.join("data", "Cost_Factor.csv"), index_col=0, header=0)
    fuel_cost = pd.read_csv(os.path.join("data", "fuel_cost.csv"), index_col=0, header=0)
    co2price = pd.read_csv(os.path.join("data", "co2_price.csv"), index_col=0)

    # Additional data to store scenario settings
    agg_p_nom_minmax = pd.read_csv(config['scenario_settings']\
                                   .get('agg_p_nom_limits'), index_col=1)
    co2030 = (1 - (co2lims[co2lims.year == 2030].co2limit.values[0] / (460 * 10**6))) * 100
    co2040 = (1 - (co2lims[co2lims.year == 2040].co2limit.values[0] / (460 * 10**6))) * 100
    co2045 = (1 - (co2lims[co2lims.year == 2045].co2limit.values[0] / (460 * 10**6))) * 100
    co2050 = (1 - (co2lims[co2lims.year == 2050].co2limit.values[0] / (460 * 10**6))) * 100

    var = [
        "regional potential",
        "CO2-reduction-2030",
        "CO2-reduction-2040",
        "CO2-reduction-2045",
        "CO2-reduction-2050",
    ]
    var.extend(list(agg_p_nom_minmax.index))

    val = [regional_potential, co2030, co2040, co2045, co2050]
    val.extend(list(agg_p_nom_minmax['max']))

    txt = pd.DataFrame({"val": val}, index=var)
    txt.to_excel(f"{bus_folder}/Scenario_settings.xlsx", index=True)

    # Read or create removal data (conventional, RES, biomass, coal, etc.)
    def read_data(n, folder_name):
        conventional_base = dp.Base_Removal_Data(n,folder_name)

        if os.path.exists(f"{folder_name}/res_basic_removal.csv"):
            RES_base_remove = pd.read_csv(f"{folder_name}/res_basic_removal.csv", index_col=0)
        else:
            _, RES_base_remove = dp.RES_data(n, folder_name)

        if os.path.exists(f"{folder_name}/res_basic_addition.csv"):
            RES_base_addition = pd.read_csv(f"{folder_name}/res_basic_addition.csv", index_col=0)
        else:
            RES_base_addition, _ = dp.RES_data(n, folder_name)

        return conventional_base, RES_base_remove, RES_base_addition

    Bio_data = dp.Biomass_data(n, name)
    conventional_base, RES_base_remove, RES_base_addition = read_data(n, name)
    coal_data = dp.Correct_coal(n, name)

    # Combine data
    conventional_base = pd.concat([conventional_base, coal_data])
    conventional_base = pd.concat([conventional_base, Bio_data])
    removal_data = pd.concat([conventional_base, RES_base_remove])
    removal_data.to_csv(f"{bus_folder}/All_removal_data.csv")
    # Make Coal/Lignite removed only based on linear phase-out
    xs=conventional_base.loc[(conventional_base.carrier=='lignite')
                          |
                          (conventional_base.carrier=='coal')].index
    conventional_base.drop(xs,inplace=True)
    # Phase-out initialization: e.g., coal by 2038, lignite by 2036
    phase_out_removal, yearly_phase_out = mp.Phase_out(n, 'coal', 2038)
    phase_out_removal_lignite, yearly_phase_out_lignite = mp.Phase_out(n, 'lignite', 2038)
    
    # Example: separate out renewables
    renewables = pd.concat([
        removal_data[removal_data.carrier=='solar'],
        removal_data[removal_data.carrier=='onwind'],
        removal_data[removal_data.carrier=='offwind-ac'],
        removal_data[removal_data.carrier=='offwind-dc']
    ])
    
    

    # Convert the network to a baseline:
    df = bf.convert_opt_to_conv(n, 2020, RES_base_addition, name=name, fuel_cost=fuel_cost)
    df_stor = bf.convert_opt_storage_to_conv(n, 2020)
    df_H2, df_H2_store = bf.H2_ready(n, 2020, fuel_cost=fuel_cost)

    # Update load, set CO2 limit, etc.
    # Example: scale to match some absolute TWh
    mp.update_load(n, 540 / (n.loads_t.p_set.sum().sum() / 1000000))
    mp.update_co2limit(n, int(co2lims.co2limit[co2lims.year == 2020]))
    mp.update_co2price(n, year=2020, co2price=co2price)

    n.lines.s_max_pu = 1.0 # Relax transmission lines contingency limit

    # Setup arrays for result tracking
    ren_perc = []
    n.storage_units.state_of_charge_initial = 0

    # Add a large "load" generator with high marginal cost to avoid infeasibilities
    n.add("Carrier", "Load")
    n.madd("Generator",
           n.buses.index[n.buses.carrier=='AC'],
           " load",
           bus=n.buses.index[n.buses.carrier=='AC'],
           carrier='load',
           marginal_cost=1e5,
           p_nom=1e6
           )

    # Setup DFs for result tracking
    gen_bar = pd.DataFrame(index=range(2020, 2051), columns=list(n.generators.carrier.unique()))
    inst_bar = pd.DataFrame(index=range(2020, 2051),
                            columns=list(n.generators.carrier[n.generators.carrier!='load'].unique()))
    store_bar = pd.DataFrame(index=range(2020, 2051), columns=list(n.storage_units.carrier.unique()))

    # Turn off cyclic SoC ==> Done Manually
    n.storage_units.cyclic_state_of_charge = False

    # Manage Regional and Yearly potential
    saved_potential = n.generators.p_nom_max[n.generators.p_nom_extendable == True]
    saved_potential = mp.Yearly_potential(n, saved_potential, regional_potential,agg_p_nom_minmax=agg_p_nom_minmax)

    # Store constraints for store e_max ==> empty at last snapshot
    p_max_pu_store = pd.DataFrame(1, index=n.snapshots, columns=n.stores.index)
    p_max_pu_store.iloc[-1] = 0
    n.pnl("Store")["e_max_pu"] = p_max_pu_store


    # H2 Imports: Scenario based
    n.generators.\
        loc[n.generators.carrier=='H2',\
            'p_nom_extendable'] = scenario_settings.get("H2_import")
    # Stop H2-Gas Mixing in CCGT: Scenario based
    n.links.\
        loc[[elem for elem in n.links.index \
             if 'H2_input' in elem],\
            'p_nom_extendable'] = scenario_settings.get("H2_ready")
    if not scenario_settings.get('H2_ready'):
        for bus in n.buses.index[n.buses.carrier=='AC']:
            n.links.loc[f"{bus} CCGT",'bus0'] = f"{bus} gas"
    
    # Incentivize Hydrogen: Scenario based
    if scenario_settings.get('H2_ready') \
        and scenario_settings.get('H2_ready_OPEX'):
            for tech in scenario_settings.get('H2_OPEX_support').keys():
                H2R.H2_Ready_opex(n,
                                  total_support=\
                                      scenario_settings\
                                          .get('H2_OPEX_support')[tech],
                                          element=tech)

    # Solve network for 2020 
    n.config = config
    n.opts = opts
    config["year"] = 2020

    n.lopf(solver_name=solver_options['name'],
           solver_options=solver_options,
           extra_functionality=extra_functionality,
           solver_dir=tmpdir)

    df = mp.append_gens(n, year=2020, df=df)
    mp.initial_storage(n)

    # Prepare to track potential changes in subsequent years
    years_cols = list(range(2021, 2051))
    Potentials_over_years = pd.DataFrame({"2020": saved_potential})
    Potentials_over_years = Potentials_over_years.reindex(columns=Potentials_over_years.columns.tolist() + years_cols)



    # The iterative optimization for 2021 to 2031, e.g. (adapt as needed):
    for i in range(2021, 2051):

        # Update lines, gens, stor
        df_H2 = mp.update_const_lines(n, i, df_H2)
        mp.update_const_gens(n)
        mp.update_const_storage(n)
        df_stor, df_H2_store = mp.append_storages(n, i, df_stor, df_H2_store)

        # Some plotting or tracking
        pt.installed_capacities(n, year=i-1, clusters=clusters,colors=colors)
        pt.Country_Map(n, year=i-1, config=config, clusters=clusters)
        ren_perc.append(pt.pie_chart(n, i-1,clusters=clusters,colors=colors))

        # Track renewable percentage
        gen_bar = pt.Gen_Bar(n, gen_bar, i-1)
        inst_bar = pt.Inst_Bar(n, inst_bar, i-1)
        store_bar = pt.storage_installation(n, store_bar, i-1)

        n.export_to_netcdf(f"Results/{str(clusters)}/{i-1}.nc")
        # Remove or reduce capacity for coal & lignite
        mp.remove_Phase_out(n, phase_out_removal, yearly_phase_out)
        mp.remove_Phase_out(n, phase_out_removal_lignite, yearly_phase_out_lignite)

        # If year == 2038, set all coal/lignite p_nom to zero
        if i == 2038:
            n.generators.loc[n.generators.carrier=='coal','p_nom'] = 0
            n.generators.loc[n.generators.carrier=='lignite','p_nom'] = 0
        #H2 only in CCGT from 2040 on
        if scenario_settings.get('H2_ready') and i >= 2041:
            H2R.H2_Mixing(n,i,
                          scenario_settings.get('H2_ready'),
                          removal_data)
        if scenario_settings.get('H2_ready') \
            and scenario_settings.get('H2_ready_CAPEX'):#implement only if both are allowed 
                CCGT_support=0 if i not in \
                        list(scenario_settings.get("H2_CAPEX_support"))\
                            else scenario_settings.get("H2_CAPEX_support")[i]
                H2R.H2_Ready_plus(n,CCGT_support)


        # Update costs, load, remove capacity
        mp.update_cost(n, i, cost_factors, fuel_cost=fuel_cost)
        mp.update_load(n, 1.01)

        mp.delete_gens(n, i, df,saved_potential,regional_potential)
        mp.delete_original_RES(n, i, renewables, saved_potential, regional_potential)
        mp.delete_storage(n, i, df_stor, df_H2, df_H2_store)
        mp.delete_old_gens(n, i, conventional_base)

        n.lines.s_max_pu = 1.0
        mp.update_co2limit(n, int(co2lims.co2limit[co2lims.year==i]))
        mp.update_co2price(n, year=i, co2price=co2price)

        config["year"] = i
        n.config = config
        n.lopf(solver_name=solver_options['name'],
               solver_options=solver_options,
               extra_functionality=extra_functionality,
               solver_dir=tmpdir)
        
        mp.initial_storage(n)
        saved_potential = mp.Yearly_potential(n, saved_potential, 
                                              regional_potential,
                                              agg_p_nom_minmax)
        Potentials_over_years.loc[:, i] = saved_potential

        df = mp.append_gens(n, i, df)

    # 10) Final updates after the myopic optimization
    mp.update_const_lines(n, i, df_H2)
    mp.update_const_gens(n)
    mp.update_const_storage(n)
    df_stor, df_H2_store = mp.append_storages(n, i, df_stor, df_H2_store)

    pt.installed_capacities(n, year=i,clusters=clusters, colors=colors)
    ren_perc.append(pt.pie_chart(n, i,clusters=clusters,colors=colors))
    pt.Country_Map(n, year=i, config=config, clusters=clusters)

    gen_bar = pt.Gen_Bar(n, gen_bar, i)
    inst_bar = pt.Inst_Bar(n, inst_bar, i)
    pt.storage_installation(n, store_bar, i)

    pt.Bar_to_PNG(gen_bar, bus_folder, "Generation",colors=colors)
    pt.Bar_to_PNG(inst_bar, bus_folder, "Installation",colors=colors)
    pt.Storage_Bar(store_bar, bus_folder,colors=colors)

    n.export_to_netcdf(f"{bus_folder}/{i}.nc")
    df.to_excel(f"{bus_folder}/addition.xlsx", index=True)

    Potentials_over_years.to_excel(f"{bus_folder}/Potentials_over_years.xlsx", index=True)

    logger.info("Model run completed successfully.")
          
if __name__ == "__main__":
    main()
