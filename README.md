# MyPyPSA-Ger
![1-s2 0-S0306261922000587-gr8_lrg](https://user-images.githubusercontent.com/60949903/179805438-f593a866-a2a9-4bd9-b0a4-33075f7bd344.jpg)


MyPyPSA-Ger, a myopic optimization model developed to represent the German energy system with a detailed mapping of the electricity sector, on a highly disaggregated level, spatially and temporally, with regional differences and investment limitations.

MyPyPSA-Ger was developed by [**Anas Abuzayed**](https://de.linkedin.com/in/anas-abuzayed-5b991aa7), at [EEW group](https://ines.hs-offenburg.de/forschung/energiesysteme-und-energiewirtschaft) at [Hochschule Offenburg](https://www.hs-offenburg.de/) . MyPyPSA-Ger model is built using the Modeling Framework [PyPSA](https://github.com/PyPSA/pypsa), with the main network being implemented from [PyPSA-Eur](https://github.com/PyPSA/pypsa-eur).

The model is described in the paper [MyPyPSA-Ger: Introducing CO2 taxes on a multi-regional myopic roadmap of the German electricity system towards achieving the 1.5 °C target by 2050](https://www.sciencedirect.com/science/article/pii/S0306261922000587), and has been used in several other publications. A YouTube course explaining basics of energy system analysis in Python is available [here](https://www.youtube.com/playlist?list=PLa98mykrHEG8MlH5hCSlB_Dpaje_m5wSY). The course material are publicly available [here](https://github.com/AnasAbuzayed) under the ESA repository.




# Installation 

## Clone the Repository 

/some/other/path % cd /some/path/without/spaces

/some/path/without/spaces % git clone https://github.com/AnasAbuzayed/MyPyPSA-Ger.git


## Install the Library

% cd MyPyPSA-Ger

% conda create --name MyPyPSA-Ger --file req.txt

## Download the supplementary data from [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.15164211.svg)](https://doi.org/10.5281/zenodo.15164211)


# How to Use the Model
### 1. To use the model, simply run the Model.py script. The basic network topology is from [PyPSA-Eur](https://github.com/PyPSA/pypsa-eur) and are stored in the repository.

### 2. To create the base network, clone into the pypsa-eur folder and create a network using the workflow management system "snakemake". For more details about how it works refer to the PyPSA-Eur documentation [here](https://pypsa-eur.readthedocs.io/en/latest/tutorial.html). The following code gives an example how to create the base network. The Model is tested with PyPSA version 22.1. Thanks to the flexibility of PyPSA and MyPyPSA-Ger, the model should work fine with any PyPSA version, unless major functionality depreciation from PyPSA took place.

![image](https://user-images.githubusercontent.com/60949903/178725004-1464261c-2a74-49a5-abeb-fba698463fef.png)

% conda activate MyPyPSA-Ger

### 3. Run MyPyPSA-Ger model

% python Model.py

% enter clusters

% 4

The results of this model will be saved in a folder within the main repository following the length of its clusters.

The model accepts clusters that represent the NUTS statistical regions of Germany. 4 Clusters is the default, with 12 GW/cluster as a default regional potential. The values could be adapted from the config file.


Many thanks for [Hamza Abo Alrob](https://github.com/haboalr) for his help on splitting the model and the functions description and for [Anna Sandhaas](https://github.com/asandhaa), Omar Elaskalani, and Martin Thomas for their help on the NUTS clustering of the model.
