import qgis
from qgis.core import *
from qgis.analysis import *
import qgis.utils
import processing
import sys, os, shutil, dill
from osgeo import ogr, gdal
import pandas as pd

user = ''
sys.path.append(f'/Users/{user}/opt/miniconda3/envs/qgis_tdi/share/qgis/python/plugins/processing/algs/gdal')
sys.path.append(f'/Users/{user}/opt/miniconda3/envs/qgis_tdi/share/qgis/python/plugins')

from Support_Functions import country_stats

# Initiating a QGIS application
qgishome = f'/Users/{user}/opt/miniconda3/envs/qgis_tdi/lib/qgis'
QgsApplication.setPrefixPath(qgishome, True)

from processing.core.Processing import Processing
Processing.initialize()
from processing.tools import *

# Set path to folder containing tiff and shapefile
folder = ''

# Set path and create folder for writing out results
metric = 'carbon_stocks' # change for different metrics
dest_dir = os.path.join(f'{folder}{metric}_results/')
if os.path.exists(dest_dir):
    pass
else:
    os.mkdir(dest_dir)

# Set path to EEZ shapefile
countries_shp = f'{folder}eez_v11_clipped.shp'

# Pull in layer from EEZ shapefile
driver = ogr.GetDriverByName('ESRI Shapefile')
dataSource = driver.Open(countries_shp, 0)
layer = dataSource.GetLayer()

# Create list of all ISO country codes in EEZ shapefile and keep on unique values
countries = []
for feature in layer:
    countries.append(feature.GetField('ISO_SOV1'))

countries_unique = list(set(countries))

# If some data has already been processed, filter processed countries out of ISO list
complete_countries = []
for filename in os.listdir(dest_dir):
    complete_countries.append(filename[:3])

countries_unique = [i for i in countries_unique if i not in complete_countries]

# Set name of tiff file for metric of interest
TIFF_file = f'Mean_carbon_stock.tif' # change for different metrics

# Calculate statistics for each country using ISO code
# Write out data for each country into a dill file
for country in countries_unique[0:]:
    stats = country_stats(country=country, TIFF=TIFF_file, folder=folder)
    
    stats_single = {}
    stats_single[f'{country}'] = stats
    with open(f'{dest_dir}{country}_stats.dill', 'wb') as f:
        dill.dump(stats_single, f)

# Combine all country statistics into one dictionary and write out as dill file
all_countries_stats = {}
for filename in os.listdir(dest_dir):
    country = filename[:3]
    with open(f'{dest_dir}{country}_stats.dill', 'rb') as f:
        stats = dill.load(f)
    all_countries_stats[country] = stats[country]

with open(f'{dest_dir}{metric}_full_stats.dill', 'wb') as f:
    dill.dump(all_countries_stats, f)

# Covert all country statistics into dataframe and write out to CSV file
countries_stats_df = pd.DataFrame.from_dict(all_countries_stats).transpose()
countries_stats_df.reset_index(inplace=True)
countries_stats_df.to_csv(f'{dest_dir}{metric}_full_stats.csv', encoding='utf-8', index=False)
