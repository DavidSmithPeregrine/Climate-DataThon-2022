from osgeo import gdal
from osgeo.gdalconst import *
import sys, os, shutil
from os.path import exists
import numpy as np

import qgis
from qgis.core import *
from qgis.analysis import *
import qgis.utils
import processing

user = ''
sys.path.append(f'/Users/{user}/opt/miniconda3/envs/qgis_tdi/share/qgis/python/plugins/processing/algs/gdal')
sys.path.append(f'/Users/{user}/opt/miniconda3/envs/qgis_tdi/share/qgis/python/plugins')

# Create QGIS funtion to select an attribute
"""
Model exported as python.
Name : Select_Attribute
With QGIS : 32000
"""

class select_attribute(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterField('Attribute', 'Attribute', type=QgsProcessingParameterField.String, parentLayerParameterName='Shapefile', allowMultiple=False, defaultValue=''))
        self.addParameter(QgsProcessingParameterString('AttributeValue', 'Attribute Value', multiLine=False, defaultValue=''))
        self.addParameter(QgsProcessingParameterVectorLayer('Shapefile', 'Shapefile', types=[QgsProcessing.TypeVectorPolygon], defaultValue=None))
        self.addParameter(QgsProcessingParameterFeatureSink('Selected_shapefile', 'Selected_Shapefile', type=QgsProcessing.TypeVectorAnyGeometry, createByDefault=True, defaultValue=None))

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(1, model_feedback)
        results = {}
        outputs = {}

        # Extract by attribute
        alg_params = {
            'FIELD': parameters['Attribute'],
            'INPUT': parameters['Shapefile'],
            'OPERATOR': 0,  # =
            'VALUE': parameters['AttributeValue'],
            'OUTPUT': parameters['Selected_shapefile']
        }
        outputs['ExtractByAttribute'] = processing.run('native:extractbyattribute', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['Selected_shapefile'] = outputs['ExtractByAttribute']['OUTPUT']
        return results

    def name(self):
        return 'Select_Attribute'

    def displayName(self):
        return 'Select_Attribute'

    def group(self):
        return 'Capstone'

    def groupId(self):
        return 'Capstone'

    def createInstance(self):
        return select_attribute()

# Mask raster image by a shapefile (cuts to outline of the shapefile)
def mask_by_shapefile(raster, shapefile, crop_file):
    OutTile = gdal.Warp(destNameOrDestDS= crop_file, srcDSOrSrcDSTab= raster, cutlineDSName=shapefile, cropToCutline=True) #, dstNodata = 0)
    OutTile = None

# Calculate mean, median, and std statistics from raster
def stats(TIFF):
    """Takes in file path for TIFF and returns a dictionary specifying mean, median, and std within extent."""
    
    tiff = gdal.Open(TIFF)
    tiff_arr = np.array(tiff.GetRasterBand(1).ReadAsArray())
    tiff_arr_corrected = np.delete(tiff_arr.flatten(), np.where(tiff_arr.flatten() < -1.e+20))

    d = {}
    d['mean'] = np.mean(tiff_arr_corrected)
    d['median'] = np.median(tiff_arr_corrected)
    d['percentile50'] = np.percentile(tiff_arr_corrected, 50)
    d['std'] = np.std(tiff_arr_corrected)

    return d

# Calculate country statistics
def country_stats(country, TIFF, folder):
    ''' Takes in country name, TIFF file name (for metric of interest), and folder path and will output a
    dictionary with the mean, median, and std of pixel values within the TIFF.
    
    country = ISO code from eez_v11_clipped.shp
    TIFF = name of TIFF file
    folder = folder containing shapefile and TIFF'''

    ## all files to be deleted will go in the tmp folder
    tmp_folder = os.path.join(f'{folder}', 'tmp/')
    if os.path.exists(tmp_folder):
        shutil.rmtree(tmp_folder)
    
    os.mkdir(tmp_folder)
    
    ## Initialize feedback and context for QGIS analyses
    feedback = QgsProcessingFeedback()
    context = QgsProcessingContext()
    
    ## Extract single country for analysis 
    attr_parameters = {'Attribute': 'ISO_SOV1',
                       'AttributeValue': f'{country}',
                       'Shapefile': f'{folder}eez_v11_clipped.shp',
                       'Selected_shapefile': f'{tmp_folder}{country}.shp'}
    attr = select_attribute()
    attr.initAlgorithm()
    attr.processAlgorithm(parameters=attr_parameters, context = context, model_feedback = feedback)

    ## Crop TIFF file to country extent
    country_shape = f'{tmp_folder}{country}.shp'
    in_TIFF = f'{folder}{TIFF}'
    TIFF_crop = f'{tmp_folder}{country}_TIFF.tif'
    mask_by_shapefile(raster=in_TIFF, shapefile=country_shape, crop_file=TIFF_crop)

    # Calculate statistics within country extent
    d = stats(TIFF = TIFF_crop)

    shutil.rmtree(tmp_folder)

    return d