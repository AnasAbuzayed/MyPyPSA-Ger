
"""
@author: anasi
main.py

This script runs the full myopic modeling process for a PyPSA-based power system model:
1) It reads user inputs (clusters, regional potential).
2) Loads the configuration YAML (solver settings, scenario opts).
3) Loads a PyPSA network from the "Networks" folder, using the user-specified number of clusters.
4) Processes data (if needed), then sets up the baseline scenario.
5) Iterates year by year, applying expansions, retirements, re-optimizations.
6) Logs and saves the final results (objective values, capacity additions, etc.) and plots.

You should have:
 - config.yaml in the same directory,
 - a "Networks" folder containing elec_s_* network files,
 - CSV data files like co2limits.csv, fuel_cost.csv, etc.

"""

import os
import logging
import pandas as pd
import yaml
import pypsa
import warnings

import data_processing as dp
import base_functions as bf
import Myopic as mp
import plotting as pt

from solve_network import extra_functionality
warnings.filterwarnings("ignore")

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def main():
    """
    Executes the myopic process from user input to final output files.
    """

    # Read config.yaml
    with open(r'config.yaml', "r") as file:
        config = yaml.load(file, Loader=yaml.FullLoader)

    tmpdir = config['solving'].get('tmpdir')
    opts = config['scenario']['opts'][0].split('-')
    solve_opts = config['solving']['options']
    solver_options = config['solving']['solver'].copy()

    # 1) Prompt user for clusters
    print("Enter clusters:")
    clusters = int(input().strip())

    # 2) Construct a network path from the "Networks" folder
    #    Example file: "Networks/elec_s_3_ec_lcopt_Co2L-1H-Ep-CCL.nc" if clusters=3
    network_filename = f"Networks/elec_s_{clusters}_ec_lcopt_Co2L-1H-Ep-CCL.nc"
    if not os.path.exists(network_filename):
        raise FileNotFoundError(f"Cannot find network file: {network_filename}")

    # 3) Prompt user for the regional potential
    print("Enter Regional potential:")
    regional_potential = float(input().strip())

    # 4) Load the PyPSA Network
    n = pypsa.Network(network_filename)
    n.generators["p_nom_min"] = 0

    # Create results folder(s)
    # For example, strip the ".nc" from network file for one folder,
    # and also create a folder named after the number of buses:
    name = network_filename[:-3]  # e.g. "Networks/elec_s_3_ec_lcopt_Co2L-1H-Ep-CCL"
    bf.createFolder(name)

    bus_folder = str(int(len(n.buses)))
    bf.createFolder(bus_folder)

    # 5) Update renewable profiles, availability, etc.
    dp.update_rens_profiles(n, reference_year=2013, name=name)
    bf.update_availability_profiles(n, name)

    # 6) Phase-out initialization: e.g., coal by 2036, lignite by 2036
    phase_out_removal, yearly_phase_out = mp.Phase_out(n, 'coal', 2036)
    phase_out_removal_lignite, yearly_phase_out_lignite = mp.Phase_out(n, 'lignite', 2036)

    # 7) Read input data / CSVs from inside the
    co2lims = pd.read_csv(os.path.join("data", "co2limits.csv"))
    cost_factors = pd.read_csv(os.path.join("data", "Cost_Factor.csv"), index_col=0, header=0)
    fuel_cost = pd.read_csv(os.path.join("data", "fuel_cost.csv"), index_col=0, header=0)
    co2price = pd.read_csv(os.path.join("data", "co2_price.csv"), index_col=0)

    # Additional data to store scenario settings
    agg_p_nom_minmax = pd.read_csv(config['electricity'].get('agg_p_nom_limits'), index_col=1)
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

    # 8) Read or create removal data (conventional, RES, biomass, coal, etc.)
    def read_data(n, folder_name):
        if os.path.exists(f"{folder_name}/conventional_basic_removal.csv"):
            conventional_base = pd.read_csv(f"{folder_name}/conventional_basic_removal.csv", index_col=0)
        else:
            conventional_base = dp.Base_Removal_Data(n)

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

    # Example: separate out renewables
    renewables = pd.concat([
        removal_data[removal_data.carrier=='solar'],
        removal_data[removal_data.carrier=='onwind'],
        removal_data[removal_data.carrier=='offwind-ac'],
        removal_data[removal_data.carrier=='offwind-dc']
    ])

    # 9) Convert the network to a baseline:
    df = bf.convert_opt_to_conv(n, 2020, RES_base_addition, name=name, fuel_cost=fuel_cost)
    df_stor = bf.convert_opt_storage_to_conv(n, 2020)
    df_H2, df_H2_store = bf.H2_ready(n, 2020, fuel_cost=fuel_cost)

    # 10) Update load, set CO2 limit, etc.
    # Example: scale to match some absolute TWh
    mp.update_load(n, 540 / (n.loads_t.p_set.sum().sum() / 1000000))

    n.lines.s_max_pu = 1.0
    mp.update_co2limit(n, int(co2lims.co2limit[co2lims.year == 2020]))
    mp.update_co2price(n, year=2020, co2price=co2price)

    # 11) Setup arrays for result tracking
    obj = []
    ren_perc = []
    n.storage_units.state_of_charge_initial = 0

    # Example: add a large "load" generator with high marginal cost
    n.add("Carrier", "Load")
    n.madd("Generator",
           n.buses.index[n.buses.carrier=='AC'],
           " load",
           bus=n.buses.index[n.buses.carrier=='AC'],
           carrier='load',
           marginal_cost=1e5,
           p_nom=1e6
           )

    gen_bar = pd.DataFrame(index=range(2020, 2051), columns=list(n.generators.carrier.unique()))
    inst_bar = pd.DataFrame(index=range(2020, 2051),
                            columns=list(n.generators.carrier[n.generators.carrier!='load'].unique()))
    store_bar = pd.DataFrame(index=range(2020, 2051), columns=list(n.storage_units.carrier.unique()))

    # Turn off cyclic SoC
    n.storage_units.cyclic_state_of_charge = False

    # 12) Manage potential
    saved_potential = n.generators.p_nom_max[n.generators.p_nom_extendable == True]
    saved_potential = mp.Yearly_potential(n, saved_potential, regional_potential,agg_p_nom_minmax=agg_p_nom_minmax)

    # Example: store constraints for store e_max at last snapshot
    p_max_pu_store = pd.DataFrame(1, index=n.snapshots, columns=n.stores.index)
    p_max_pu_store.iloc[-1] = 0
    n.pnl("Store")["e_max_pu"] = p_max_pu_store


    n.links.loc[[elem for elem in n.links.index if 'H2_input' in elem], 'p_nom_extendable'] = False
    n.generators.loc[n.generators.carrier=='H2','p_nom_extendable'] = False
    if not n.links.loc[[elem for elem in n.links.index if 'H2_input' in elem],'p_nom_extendable'].any():
        for bus in n.buses.index[n.buses.carrier=='AC']:
            n.links.loc[f"{bus} CCGT",'bus0'] = f"{bus} gas"

    # Example: Solve network for 2020 
    n.config = config
    n.opts = opts
    config["year"] = 2020

    n.lopf(solver_name="gurobi",
           solver_options=solver_options,
           extra_functionality=extra_functionality,
           solver_dir=tmpdir)

    df = mp.append_gens(n, year=2020, df=df)
    mp.initial_storage(n)

    # Prepare to track potential changes in subsequent years
    years_cols = list(range(2021, 2051))
    Potentials_over_years = pd.DataFrame({"2020": saved_potential})
    Potentials_over_years = Potentials_over_years.reindex(columns=Potentials_over_years.columns.tolist() + years_cols)

    # Example objective: subtract the big "load generator" cost from the objective
    load_cost = n.generators_t.p[n.generators.index[n.generators.carrier=='load']].sum().sum()
    obj.append(n.objective - load_cost * n.generators.marginal_cost.max())

    networks = []

    # 13) The iterative loop for 2021 to 2031, e.g. (adapt as needed):
    for i in range(2021, 2032):

        # Remove or reduce capacity for coal & lignite
        mp.remove_Phase_out(n, phase_out_removal, yearly_phase_out)
        mp.remove_Phase_out(n, phase_out_removal_lignite, yearly_phase_out_lignite)

        # If year == 2036, set all coal/lignite p_nom to zero
        if i == 2036:
            n.generators.loc[n.generators.carrier=='coal','p_nom'] = 0
            n.generators.loc[n.generators.carrier=='lignite','p_nom'] = 0

        # Update lines, gens, stor
        df_H2 = mp.update_const_lines(n, i, df_H2)
        mp.update_const_gens(n)
        mp.update_const_storage(n)
        df_stor, df_H2_store = mp.append_storages(n, i, df_stor, df_H2_store)

        # Some plotting or tracking
        pt.installed_capacities(n, year=i-1, clusters=clusters)
        pt.Country_Map(n, year=i-1, config=config, clusters=clusters)  # custom function

        # Optionally track renewable percentage
        # ren_perc.append(pie_chart(n, i-1, clusters=clusters))

        gen_bar = pt.Gen_Bar(n, gen_bar, i-1)
        inst_bar = pt.Inst_Bar(n, inst_bar, i-1)
        store_bar = pt.storage_installation(n, store_bar, i-1)

        networks.append(n)
        directory = str(clusters)
        n.export_to_netcdf(f"{directory}/{i-1}.nc")

        # Update costs, load, remove capacity
        mp.update_cost(n, i, cost_factors, fuel_cost=fuel_cost)
        mp.update_load(n, 1.01)

        mp.delete_gens(n, i, df)
        mp.delete_original_RES(n, i, renewables, saved_potential, regional_potential)
        mp.delete_storage(n, i, df_stor, df_H2, df_H2_store)
        mp.delete_old_gens(n, i, conventional_base)

        n.lines.s_max_pu = 1.0
        mp.update_co2limit(n, int(co2lims.co2limit[co2lims.year==i]))
        mp.update_co2price(n, year=i, co2price=co2price)

        config["year"] = i
        n.config = config
        n.lopf(solver_name="gurobi",
               solver_options=solver_options,
               extra_functionality=extra_functionality,
               solver_dir=tmpdir)
        
        mp.initial_storage(n)
        saved_potential = mp.Yearly_potential(n, saved_potential, regional_potential)
        Potentials_over_years.loc[:, i] = saved_potential

        df = mp.append_gens(n, i, df)
        load_cost = n.generators_t.p[n.generators.index[n.generators.carrier=='load']].sum().sum()
        obj.append(n.objective - load_cost * n.generators.marginal_cost.max())

    # 14) Final updates after the loop
    mp.update_const_lines(n, i, df_H2)
    mp.update_const_gens(n)
    mp.update_const_storage(n)
    df_stor, df_H2_store = mp.append_storages(n, i, df_stor, df_H2_store)

    pt.installed_capacities(n, year=i)
    ren_perc.append(pt.pie_chart(n, i))
    pt.Country_Map(n, year=i)

    gen_bar = pt.Gen_Bar(n, gen_bar, i)
    inst_bar = pt.Inst_Bar(n, inst_bar, i)
    pt.storage_installation(n, store_bar, i)

    pt.Bar_to_PNG(gen_bar, name, "Generation")
    pt.Bar_to_PNG(inst_bar, name, "Installation")
    pt.Storage_Bar(store_bar, name)

    networks.append(n)
    n.export_to_netcdf(f"{int(len(n.buses)/7)}/{i}.nc")
    df.to_excel(f"{int(len(n.buses)/7)}/addition.xlsx", index=True)

    objective = pd.DataFrame({
        'year': list(range(2020, 2051)),
        'objective': obj,
        'RES_mix': ren_perc
    })
    objective.to_excel(f"{int(len(n.buses)/4)}/objective.xlsx", index=False)
    Potentials_over_years.to_excel(f"{int(len(n.buses)/4)}/Potentials_over_years.xlsx", index=True)

    logger.info("Model run completed successfully.")
          
if __name__ == "__main__":
    main()
