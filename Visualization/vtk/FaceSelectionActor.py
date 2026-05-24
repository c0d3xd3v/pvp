import vtkmodules.all as vtk
import numpy as np
from vtkmodules.util.numpy_support import vtk_to_numpy, numpy_to_vtk

class FaceSelectionActor(vtk.vtkActor):
    def __init__(self):
        super().__init__()
        self.full_polydata = None
        self.current_mode = "cell"          # 'cell' or 'partition'
        self.lut = None

        self.mapper = vtk.vtkOpenGLPolyDataMapper()
        self.SetMapper(self.mapper)
        self.GetProperty().SetInterpolationToFlat()
        self.SetPickable(True)

    def setPolyData(self, polydata: vtk.vtkPolyData, partition_ids: np.ndarray = None):
        # ---- Add OriginalIds (cell indices) ----
        id_filter = vtk.vtkIdFilter()
        id_filter.SetInputData(polydata)
        id_filter.SetCellIds(True)
        id_filter.SetPointIds(False)
        id_filter.SetCellIdsArrayName("OriginalIds")
        id_filter.Update()
        self.full_polydata = id_filter.GetOutput()

        # ---- Add PartitionIds if provided ----
        if partition_ids is not None:
            self._add_partition_array(partition_ids)

        # ---- Determine max ID for LUT ----
        num_cells = self.full_polydata.GetNumberOfCells()
        max_id = num_cells - 1                     # OriginalIds go from 0..num_cells-1
        if partition_ids is not None and len(partition_ids) > 0:
            max_id = max(max_id, np.max(partition_ids))

        # ---- Create LUT covering the whole range ----
        self._create_lut(max_id + 1)

        # ---- Start with cell mode ----
        self.setColorMode("partition")

    def _add_partition_array(self, partition_ids: np.ndarray):
        """Replace or add the PartitionIds array."""
        # Remove old if exists
        old = self.full_polydata.GetCellData().GetArray("PartitionIds")
        if old:
            self.full_polydata.GetCellData().RemoveArray("PartitionIds")
        # Add new
        vtk_ids = numpy_to_vtk(partition_ids, deep=True, array_type=vtk.VTK_INT)
        vtk_ids.SetName("PartitionIds")
        self.full_polydata.GetCellData().AddArray(vtk_ids)

    def updatePartitions(self, face_ids, new_partition_id):
        """
        Setzt für alle Zellen in face_ids (Liste oder numpy-Array von OriginalIds)
        die Partition‑ID auf new_partition_id.
        """
        if self.full_polydata is None:
            return

        # 1. Aktuelles PartitionIds‑Array holen (als numpy‑Array)
        part_arr = self.full_polydata.GetCellData().GetArray("PartitionIds")
        if part_arr is None:
            raise RuntimeError("PartitionIds array not found. Call setPolyData with partition_ids first.")

        part_np = vtk_to_numpy(part_arr)

        # 2. Für jede angegebene Zelle die Partition‑ID ändern
        #    face_ids sind OriginalIds (entsprechen den Zell‑Indizes im full_polydata)
        for cell_id in face_ids:
            part_np[cell_id] = new_partition_id

        # 3. Array im Polydata ersetzen (Änderungen müssen zurück nach VTK)
        new_vtk_arr = numpy_to_vtk(part_np, deep=True, array_type=vtk.VTK_INT)
        new_vtk_arr.SetName("PartitionIds")
        self.full_polydata.GetCellData().RemoveArray("PartitionIds")
        self.full_polydata.GetCellData().AddArray(new_vtk_arr)

        # 4. Falls aktuell der Partition‑Modus aktiv ist, Mapper aktualisieren
        if self.current_mode == "partition":
            self.setColorMode("partition")   # löst Neuzeichnen aus
        else:
            # Auch im Zell‑Modus muss die LUT evtl. erweitert werden,
            # wenn new_partition_id größer ist als bisherige max_id.
            # Falls nicht, reicht ein simples Update des Mappers:
            self.mapper.Modified()

    def _create_lut(self, num_entries):
        self.lut = vtk.vtkLookupTable()
        self.lut.SetNumberOfTableValues(num_entries)
        self.lut.SetRange(0, num_entries - 1)
        self.lut.Build()
        for i in range(num_entries):
            r, g, b = np.random.random(3)
            self.lut.SetTableValue(i, r, g, b, 1.0)

    def setColorMode(self, mode: str):
        """mode = 'cell' (OriginalIds) or 'partition' (PartitionIds)"""
        if mode not in ("cell", "partition"):
            raise ValueError("Mode must be 'cell' or 'partition'")

        self.current_mode = mode

        # Choose which scalar array to use
        if mode == "cell":
            self.full_polydata.GetCellData().SetActiveScalars("OriginalIds")
        else:  # partition
            # If PartitionIds array does not exist, fall back to OriginalIds
            if self.full_polydata.GetCellData().GetArray("PartitionIds") is None:
                print("Warning: PartitionIds array missing, using OriginalIds instead.")
                self.full_polydata.GetCellData().SetActiveScalars("OriginalIds")
            else:
                self.full_polydata.GetCellData().SetActiveScalars("PartitionIds")

        self.mapper.SetInputData(self.full_polydata)
        self.mapper.SetScalarModeToUseCellData()
        self.mapper.SetLookupTable(self.lut)
        # Range is always 0 .. num_entries-1 (LUT covers all)
        self.mapper.SetScalarRange(0, self.lut.GetNumberOfTableValues() - 1)
        self.mapper.Modified()

    # Optional: edge rendering
    def enableEdges(self):
        p = self.GetProperty()
        colors = vtk.vtkNamedColors()
        edgeColor = colors.GetColor3d("Black")
        p.SetEdgeColor(edgeColor)
        self.mapper.SetResolveCoincidentTopologyToPolygonOffset()
        self.mapper.SetResolveCoincidentTopologyLineOffsetParameters(100.0, 10.0)
        p.EdgeVisibilityOn()

    def disableEdges(self):
        self.GetProperty().EdgeVisibilityOff()
