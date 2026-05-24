import vtk
import numpy
from vtkmodules.util import numpy_support

def find_neighbors_in_radius(point_cloud:numpy.ndarray, radius:float):
    print("select points")
    try:
       import mhno.point_cloud_tools_pybind11 as pct 
       neighbours = pct.find_neighbors_in_radius(point_cloud, radius)
       return neighbours
    except:
       print('error, fallback is not selecting ...')
       return []
