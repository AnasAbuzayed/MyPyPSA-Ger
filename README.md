# MyPyPSA-Ger
MyPyPSA-Ger

MyPyPSA-Ger, a myopic optimization model developed to represent the German energy system with a detailed mapping of the electricity sector, on a highly disaggregated level, spatially and temporally, with regional differences and investment limitations.

MyPyPSA-Ger was built using the Modeling Framework [PyPSA](https://github.com/PyPSA/pypsa), and upon [PyPSA-Eur](https://github.com/PyPSA/pypsa-eur).

The model is described in the paper [MyPyPSA-Ger: Introducing CO2 taxes on a multi-regional myopic roadmap of the German electricity system towards achieving the 1.5 °C target by 2050](https://www.sciencedirect.com/science/article/pii/S0306261922000587)




# Installation 

## Clone the Repository 

/some/other/path % cd /some/path/without/spaces

/some/path/without/spaces % git clone https://github.com/AnasAbuzayed/MyPyPSA-Ger.git


## Install the Library

%cd MyPyPSA-Ger

conda install --name MyPyPSA-Ger --file req.txt

## Use the Model
% conda activate MyPyPSA-Ger

% python Model.py

Enter the Network Name & Regional Potential Value
The main network for the model is created through [PyPSA-Eur](https://github.com/PyPSA/pypsa-eur). After obtaining the network, the model MyPyPSA-Ger can be further used

![image](https://user-images.githubusercontent.com/60949903/178725004-1464261c-2a74-49a5-abeb-fba698463fef.png)

