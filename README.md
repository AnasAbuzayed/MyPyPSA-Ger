# MyPyPSA-Ger
MyPyPSA-Ger

MyPyPSA-Ger, a myopic optimization model developed to represent the German energy system with a detailed mapping of the electricity sector, on a highly disaggregated level, spatially and temporally, with regional differences and investment limitations.

MyPyPSA-Ger was developed by [EEW group](https://ines.hs-offenburg.de/forschung/energiesysteme-und-energiewirtschaft) at [Hochschule Offenburg] (https://www.hs-offenburg.de/). MyPyPSA-Ger model is built using the Modeling Framework [PyPSA](https://github.com/PyPSA/pypsa), and upon [PyPSA-Eur](https://github.com/PyPSA/pypsa-eur).

The model is described in the paper [MyPyPSA-Ger: Introducing CO2 taxes on a multi-regional myopic roadmap of the German electricity system towards achieving the 1.5 °C target by 2050](https://www.sciencedirect.com/science/article/pii/S0306261922000587)




# Installation 

## Clone the Repository 

/some/other/path % cd /some/path/without/spaces

/some/path/without/spaces % git clone https://github.com/AnasAbuzayed/MyPyPSA-Ger.git


## Install the Library

% cd MyPyPSA-Ger

% conda create --name MyPyPSA-Ger --file req.txt

## Use the Model
### 1. To use the model, first we need to create the base network using [PyPSA-Eur](https://github.com/PyPSA/pypsa-eur). You need to install the cutouts and data to be used in the model, either by running the code below or manually from [Zenodo](https://zenodo.org/record/6827030#.YtFzv3bP1zo).

% cd MyPyPSA-Ger

% python pypsa-eur-data.py

### 2. To create the base network, clone into the pypsa-eur folder and create a network using the workflow management system "snakemake". For more details about how it works refer to the PyPSA-Eur documentation [here](https://pypsa-eur.readthedocs.io/en/latest/tutorial.html). The following code gives an example how to create the base network. The base network is built and tested using PyPSA-Eur V0.2.0, the current PyPSA-Eur version will be tested with MyPyPSA-Ger later on. 

![image](https://user-images.githubusercontent.com/60949903/178725004-1464261c-2a74-49a5-abeb-fba698463fef.png)

% conda activate MyPyPSA-Ger

% cd pypsa-eur

% snakemake results/networks/elec_s_6_ec_lcopt_Co2L-1H-Ep-CCL.nc --cores --keep-target-files

The resulted network will now be in the path MyPyPSA-Ger/pypsa-eur/results/networks.

### 3. Run MyPyPSA-Ger model

% cd ..

% python Model.py

% enter data network name

% elec_s_6_ec_lcopt_Co2L-1H-Ep-CCL.nc

% enter regional potential value

% 8500

The results of this model will be saved in a folder within the main repository under the exact name of the network.
