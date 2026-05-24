import vtk
from vtkmodules.util import numpy_support


def poission_sampling(poly_mesh:vtk.vtkPolyData, num_samples:int=5000):
    try:
        import mhno.point_cloud_tools_pybind11 as pct 

        retrieved_points = poly_mesh.GetPoints()
        numpy_points = numpy_support.vtk_to_numpy(retrieved_points.GetData())

        cells = poly_mesh.GetPolys()
        idList = vtk.vtkIdList()
        cells.InitTraversal()

        triangles_only = True
        triangles = []
        while cells.GetNextCell(idList):
            num_ids = idList.GetNumberOfIds()
            if num_ids != 3:
                triangles_only = False
                break
            else:
                triangles.append([idList.GetId(0), idList.GetId(1), idList.GetId(2)])

        print(f'triangles only : {triangles_only}')

        sampled_points = pct.poisson_sampling(num_samples, numpy_points, triangles)
        print(f'sampled_points : {len(sampled_points)}')
        return sampled_points
    except:
        print('error, fallback is not sampling ...')
        return []
