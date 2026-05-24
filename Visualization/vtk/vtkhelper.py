import time
import random
import numpy as np

from vtkmodules.util.numpy_support import numpy_to_vtk

from vtkmodules.vtkRenderingAnnotation import (
    vtkAnnotatedCubeActor,
    vtkAxesActor
)
from vtkmodules.vtkRenderingCore import (
    vtkActor,
    vtkPolyDataMapper,
    vtkPropAssembly,
    vtkRenderWindow,
    vtkRenderWindowInteractor,
    vtkRenderer
)
import vtk
import xml.etree.ElementTree as ET


def make_axes_actor(scale, xyz_labels):
    """
    :param scale: Sets the scale and direction of the axes.
    :param xyz_labels: Labels for the axes.
    :return: The axes actor.
    """
    axes = vtkAxesActor()
    axes.SetScale(scale)
    axes.SetShaftTypeToCylinder()
    axes.SetCylinderRadius(1.5 * axes.GetCylinderRadius())
    axes.SetConeRadius(2.0 * axes.GetConeRadius())
    axes.SetSphereRadius(1.5 * axes.GetSphereRadius())
    axes.AxisLabelsOff()
    return axes


def make_annotated_cube_actor(cube_labels, colors):
    """
    :param cube_labels: The labels for the cube faces.
    :param colors: Used to determine the cube color.
    :return: The annotated cube actor.
    """
    # A cube with labeled faces.
    cube = vtkAnnotatedCubeActor()
    cube.SetXPlusFaceText(cube_labels[0])
    cube.SetXMinusFaceText(cube_labels[1])
    cube.SetYPlusFaceText(cube_labels[2])
    cube.SetYMinusFaceText(cube_labels[3])
    cube.SetZPlusFaceText(cube_labels[4])
    cube.SetZMinusFaceText(cube_labels[5])
    cube.SetFaceTextScale(0.5)
    cube.GetCubeProperty().SetColor(colors.GetColor3d('Gainsboro'))

    cube.GetTextEdgesProperty().SetColor(colors.GetColor3d('LightSlateGray'))

    # Change the vector text colors.
    cube.GetXPlusFaceProperty().SetColor(colors.GetColor3d('Tomato'))
    cube.GetXMinusFaceProperty().SetColor(colors.GetColor3d('Tomato'))
    cube.GetYPlusFaceProperty().SetColor(colors.GetColor3d('DeepSkyBlue'))
    cube.GetYMinusFaceProperty().SetColor(colors.GetColor3d('DeepSkyBlue'))
    cube.GetZPlusFaceProperty().SetColor(colors.GetColor3d('SeaGreen'))
    cube.GetZMinusFaceProperty().SetColor(colors.GetColor3d('SeaGreen'))
    return cube


def make_cube_actor(label_selector, colors):
    """
    :param label_selector: The selector used to define labels for the axes and cube.
    :param colors: Used to set the colors of the cube faces.
    :return: The combined axes and annotated cube prop.
    """
    if label_selector == 'sal':
        # xyz_labels = ['S', 'A', 'L']
        xyz_labels = ['+X', '+Y', '+Z']
        cube_labels = ['S', 'I', 'A', 'P', 'L', 'R']
        scale = [1.5, 1.5, 1.5]
    elif label_selector == 'rsp':
        # xyz_labels = ['R', 'S', 'P']
        xyz_labels = ['+X', '+Y', '+Z']
        cube_labels = ['R', 'L', 'S', 'I', 'P', 'A']
        scale = [1.5, 1.5, 1.5]
    elif label_selector == 'lsa':
        # xyz_labels = ['L', 'S', 'A']
        xyz_labels = ['+X', '+Y', '+Z']
        cube_labels = ['L', 'R', 'S', 'I', 'A', 'P']
        scale = [1.5, 1.5, 1.5]
    else:
        xyz_labels = ['+X', '+Y', '+Z']
        cube_labels = ['+X', '-X', '+Y', '-Y', '+Z', '-Z']
        scale = [1.5, 1.5, 1.5]

    # We are combining a vtkAxesActor and a vtkAnnotatedCubeActor
    # into a vtkPropAssembly
    cube = make_annotated_cube_actor(cube_labels, colors)
    axes = make_axes_actor(scale, xyz_labels)

    # Combine orientation markers into one with an assembly.
    assembly = vtkPropAssembly()
    assembly.AddPart(axes)
    assembly.AddPart(cube)
    return assembly


# Funktion zum Erstellen eines vtkColorTransferFunction aus XML
def create_color_transfer_function_from_xml(xml_file):
    colorTransferFunction = vtk.vtkColorTransferFunction()
    
    root = ET.fromstring(xml_file)

    for point in root.iter("Point"):
        x = float(point.get("x"))
        r = float(point.get("r"))
        g = float(point.get("g"))
        b = float(point.get("b"))
        colorTransferFunction.AddRGBPoint(x, r, g, b)
    
    color_steps = 32
    # Erstellen einer VTK-Lookup-Tabelle (LookupTable) basierend auf der Farbtransferfunktion
    lut = vtk.vtkLookupTable()
    lut.SetNumberOfTableValues(color_steps)  # Anzahl der Werte in der LUT (z.B. 256 für 8-Bit Farbtiefe)
    lut.Build()

    # Anwenden der Farbtransferfunktion auf die Lookup-Tabelle
    for i in range(color_steps):
        x = i / (color_steps - 1.0)  # Skalieren auf den Bereich [0, 1]
        color = colorTransferFunction.GetColor(x)
        lut.SetTableValue(i, color[0], color[1], color[2], 1.0)  # Alpha auf 1.0 (undurchsichtig) festlegen

    colorTransferFunction.SetVectorModeToMagnitude()
    lut.SetVectorModeToMagnitude()
    return colorTransferFunction, lut


def iglToVtkPolydata(sf, sv):
    triangle_polydata = vtk.vtkPolyData()

    points_array = numpy_to_vtk(sv, deep=True)

    _sf = np.array(sf)
    nbpts = np.full(_sf.shape[0], 3)
    _sf = np.column_stack((nbpts, _sf))

    triangles_array = numpy_to_vtk(_sf, deep=True, array_type=vtk.VTK_ID_TYPE)

    points = vtk.vtkPoints()
    points.SetData(points_array)

    cells2 = vtk.vtkCellArray()
    cells2.SetCells(triangles_array.GetNumberOfTuples(), triangles_array)

    # Fügen Sie die Punkte und Zellen zur PolyData hinzu
    triangle_polydata.SetPoints(points)
    triangle_polydata.SetPolys(cells2)
    return triangle_polydata


def addRandomCellData(triangle_polydata):
    tgroupping = vtk.vtkFloatArray()
    tgroupping.SetNumberOfComponents(1)
    tgroupping.SetName("group")

    n = triangle_polydata.GetNumberOfCells()
    for i in range(n):
        tgroupping.InsertNextTuple1(random.random())
    
    triangle_polydata.GetCellData().SetScalars(tgroupping)

    return triangle_polydata


def addScalarCellData(triangle_polydata, cell_data, name):
    t_start = time.time()
    points_array = numpy_to_vtk(cell_data, deep=True)
    points_array.SetName(name)
    triangle_polydata.GetPointData().AddArray(points_array)
    print("copy time : ", time.time() - t_start, name)
    return triangle_polydata


def read_cubemap(cubemap):
    """
    Read six images forming a cubemap.

    :param cubemap: The paths to the six cubemap files.
    :return: The cubemap texture.
    """
    cube_map = vtk.vtkTexture()
    cube_map.CubeMapOn()

    i = 0
    for fn in cubemap:
        # Read the images.
        reader_factory = vtk.vtkImageReader2Factory()
        img_reader = reader_factory.CreateImageReader2(str(fn))
        img_reader.SetFileName(str(fn))

        # Each image must be flipped in Y due to canvas
        #  versus vtk ordering.
        flip = vtk.vtkImageFlip()
        flip.SetInputConnection(img_reader.GetOutputPort(0))
        flip.SetFilteredAxis(1)  # flip y axis
        cube_map.SetInputConnection(i, flip.GetOutputPort())
        i += 1

    cube_map.MipmapOn()
    cube_map.InterpolateOn()

    return cube_map


def read_equirectangular_file(fn_path):
    """
    Read an equirectangular environment file and convert to a texture.

    :param fn_path: The equirectangular file path.
    :return: The texture.
    """
    texture = vtk.vtkTexture()

    #suffix = fn_path.suffix.lower()
    #if suffix in ['.jpeg', '.jpg', '.png']:
    reader_factory = vtk.vtkImageReader2Factory()
    img_reader = reader_factory.CreateImageReader2(str(fn_path))
    img_reader.SetFileName(str(fn_path))

    texture.SetInputConnection(img_reader.GetOutputPort(0))
    '''
    else:
        reader = vtk.vtkHDRReader()
        extensions = reader.GetFileExtensions()
        # Check the image can be read.
        if not reader.CanReadFile(str(fn_path)):
            print('CanReadFile failed for ', fn_path)
            return None
        if suffix not in extensions:
            print('Unable to read this file extension: ', suffix)
            return None
        reader.SetFileName(str(fn_path))

        texture.SetColorModeToDirectScalars()
        texture.SetInputConnection(reader.GetOutputPort())
    '''

    texture.MipmapOn()
    texture.InterpolateOn()

    return texture


def read_unstructured_grid(file_path):
    if file_path.endswith(".vtk"):
        reader = vtk.vtkUnstructuredGridReader()
    elif file_path.endswith(".vtu"):
        reader = vtk.vtkXMLUnstructuredGridReader()
    else:
        raise ValueError("Unsupported file format. Please use a .vtk or .vtu file.")

    reader.SetFileName(file_path)
    reader.Update()

    unstructured_grid = reader.GetOutput()

    return unstructured_grid
    