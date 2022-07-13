# PyPSA-Eur: An Open Optimisation Model of the European Transmission System

The model is described in the [documentation](https://pypsa-eur.readthedocs.io)
and in the paper
[PyPSA-Eur: An Open Optimisation Model of the European Transmission
System](https://arxiv.org/abs/1806.01613), 2018,
[arXiv:1806.01613](https://arxiv.org/abs/1806.01613).


The Model is used as a basis for MyPyPSA-Ger to create the basic network of Germany.
following settings are set in the config file in order to correctly use the model.


1. extendable carriers: Generator: use CCGT or OCGT.
2. Store or StorageUnit as extendable is not yet implemented in the model

Other settings are already in default settings for use in MyPyPSA-Ger.
