# -*- coding: utf-8 -*-
"""
Created on Wed Jul 13 14:20:24 2022

@author: aabuzay1
"""

import os
import requests
from zipfile import ZipFile


if os.path.exists('pypsa-eur/pypsa-eur-master.zip'):
    pass
else:
    URL = "https://zenodo.org/record/6827030/files/pypsa-eur-master.zip"
    filename = os.path.basename(URL)
    
    response = requests.get(URL, stream=True)
    
    if response.status_code == 200:
        with open('pypsa-eur/'+filename, 'wb') as out:
            out.write(response.content)
    else:
        print('Request failed: %d' % response.status_code)


with ZipFile('pypsa-eur-master.zip', 'r') as zipObj:
   # Extract all the contents of zip file in current directory
   zipObj.extractall(path='pypsa-eur/')

