import vtkmodules.all as vtk
from Visualization.vtk.vtkhelper import *
import numpy as np
import math
from vtkmodules.util.numpy_support import vtk_to_numpy, numpy_to_vtk

from PySide6.QtCore import QFile

class NgSolveResultActor(vtk.vtkActor):
    def __init__(self):
        self.dataset = None
        self.__center = (0., 0., 0.)
        self.clipPlane = vtk.vtkPlane()
        self.gridToPolyData = vtk.vtkGeometryFilter()
        self.normals = vtk.vtkPolyDataNormals()
        # Lade die XML-Datei aus den Ressourcen
        qrc_path = ":/colormaps/color_theme.xml"
        file = QFile(qrc_path)
        if not file.open(QFile.ReadOnly | QFile.Text):
            print(f"Could not open resource file: {qrc_path}")
            return None
        xml_data = file.readAll().data().decode()
        self.colorTransferFunction, self.lut = create_color_transfer_function_from_xml(xml_data)
        self.colorTransferFunction.SetVectorModeToMagnitude()
        self.mapper = vtk.vtkOpenGLPolyDataMapper()
        self.isFieldVectorValued = False
        self.texture_image_reader = None
        self.clipper = None
        self.texture = None
        self.tcoords = None
        self.prgfilter = None
        self.pdata = None

    def setDataset(self, dataset):
        self.dataset = dataset
        self.__center = dataset.GetCenter()
        xnorm = [1.0, 0.0, 0.0]
        self.clipPlane = vtk.vtkPlane()
        self.clipPlane.SetOrigin(self.__center)
        self.clipPlane.SetNormal(xnorm)
        self.clipper = self.setupClipping(dataset, self.__center)
        self.gridToPolyData = self.toPolyData(self.clipper.GetOutput())
        self.normals = self.setupNormals(self.gridToPolyData.GetOutputPort())
        self.pdata = self.normals.GetOutput()

        self.prgfilter = vtk.vtkProgrammableFilter()
        self.prgfilter.SetInputData(self.pdata)
        self.time = 1.0
        self.amp = 1.0
        
        self.mapper = self.__setupMapper(self.pdata)
        self.__setupActor(self.mapper)

        self.disableClipping()

    def enableClipping(self):
        self.gridToPolyData.SetInputData(self.clipper.GetOutput())
        self.gridToPolyData.Update()
        self.normals.Update()

    def disableClipping(self):
        self.gridToPolyData.SetInputData(self.dataset)
        self.gridToPolyData.Update()
        self.normals.Update()

    def enableEdges(self):
        p = self.GetProperty() # vtk.vtkProperty()
        colors = vtk.vtkNamedColors()
        edgeColor = colors.GetColor3d("Black")
        p.SetEdgeColor(edgeColor)
        self.mapper.SetResolveCoincidentTopologyToPolygonOffset()
        self.mapper.SetResolveCoincidentTopologyLineOffsetParameters(100.0, 10.0)
        p.EdgeVisibilityOn()
        #p.SetEdgeOpacity(1.0)
        #self.mapper.SetColorModeToDefault()

    def disableEdges(self):
        self.GetProperty().EdgeVisibilityOff()

    def setupClipping(self, dataset, center):
        clipper = vtk.vtkClipDataSet()
        clipper.SetInputData(dataset)
        clipper.SetClipFunction(self.clipPlane)
        clipper.SetValue(0.0)
        clipper.GenerateClippedOutputOff()
        clipper.GenerateClipScalarsOff()
        clipper.Update()

        return clipper

    def toPolyData(self, datasetport):
        gridToPolyData = vtk.vtkGeometryFilter()
        gridToPolyData.SetInputData(datasetport)
        gridToPolyData.Update()

        return gridToPolyData

    def setupNormals(self, datasetport):
        normals = vtk.vtkPolyDataNormals()
        normals.SetInputConnection(datasetport)
        normals.AutoOrientNormalsOn()
        normals.ConsistencyOn()
        normals.ComputePointNormalsOn()
        normals.SplittingOn()
        #normals.ComputeCellNormalsOn()
        normals.Update()

        return normals

    def select_function(self, name):
        self.function_name = name
        self.mapper.SelectColorArray(self.function_name)
        f = self.dataset.GetPointData().GetArray(self.function_name)
        real = vtk_to_numpy(f)
        self.isFieldVectorValued = True if f.GetNumberOfComponents() > 1 else False
        range = [0, np.max(real)] if self.isFieldVectorValued else [np.min(real), np.max(real)] 
        self.mapper.SetScalarRange(range)
        if self.isFieldVectorValued:
            self.prgfilter.SetExecuteMethod(self.vectorFieldAnimation)
        else:
            self.prgfilter.SetExecuteMethod(self.scalarFieldAnimation)
        self.updateRendering()

    def apply_vector_field_on_position(self, should_apply, scale):
        if should_apply:
            self.amp = scale
        else:
            self.amp = 0.0
        self.updateRendering()

    def get_field_names(self):
        array_names = []
        for n in range(field_data.GetNumberOfArrays()):
            array_names.append(field_data.GetArrayName(n))
        return array_names

    def __setupMapper(self, dataset):
        mapper = vtk.vtkOpenGLPolyDataMapper()
        mapper.SetInputData(self.pdata)
        mapper.SetScalarModeToDefault()
        mapper.ScalarVisibilityOn()
        mapper.SetScalarModeToUsePointFieldData()
        mapper.InterpolateScalarsBeforeMappingOn()
        mapper.SetLookupTable(self.lut)
        return mapper

    def __setupActor(self, mapper):
        #actor = vtk.vtkActor()
        self.SetMapper(mapper)
        prop: vtk.vtkProperty = self.GetProperty()
        prop.SetInterpolationToFlat()
        prop.SetMetallic(1.0)
        prop.SetRoughness(0.2)
        prop.SetDiffuse(0.9)
        prop.SetBaseIOR(0.5)
        prop.SetCoatStrength(0.2)
        prop.SetCoatIOR(0.5)
        white = vtk.vtkNamedColors().GetColor3d('White')
        prop.SetColor(white)
        bgcolor = vtk.vtkNamedColors().HTMLColorToRGB("#363737")
        bgcolor = [bgcolor[0]/255., bgcolor[1]/255., bgcolor[2]/255.]
        prop.SetEdgeColor(white)
        prop.SetCoatRoughness(0.0)
        prop.SetCoatColor(vtk.vtkNamedColors().GetColor3d('White'))
        self.SetPickable(True)

    def GetCenter(self):
        return self.__center

    def updateRendering(self):
        self.normals.Modified()
        self.prgfilter.Modified()
        self.mapper.Modified()

        self.normals.Update()
        self.prgfilter.Update()
        self.mapper.Update()

    def setAnimationTime(self, t):
        self.time = t

    def scalarFieldAnimation(self):
        print("not implemented")
        pass

    def vectorFieldAnimation(self):
        input_data = self.prgfilter.GetInputDataObject(0, 0)
        output_data = self.prgfilter.GetOutputDataObject(0)

        points = vtk_to_numpy(input_data.GetPoints().GetData())
        f = vtk_to_numpy(input_data.GetPointData().GetArray(self.function_name))
        result = points + f*np.cos(self.time*2.0*math.pi)*self.amp

        result_array_vtk = numpy_to_vtk(result, deep=True)
        output_data.GetPoints().SetData(result_array_vtk)
