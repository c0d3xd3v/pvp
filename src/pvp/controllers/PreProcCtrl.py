from PySide6.QtCore import Slot, Signal, QObject, QUrl

from pvp.fileio.formats import EXPORT_FORMATS
from pvp.model.project import Project
from pvp.services import export, project_ops
from pvp.services.boundary_transfer import BoundarySnapshot


def _local_path(path: str) -> str:
    # QML passes file URLs ("file:///...") from its dialogs
    return QUrl(path).toLocalFile() if path.startswith("file:") else path


class PreProcCtrl(QObject):
    """QML-facing side of the pre-processing project: runs the project
    operations and shows the result in the scene."""
    sessionChanged = Signal()
    partitionsChanged = Signal()

    def __init__(self, project: Project, scene_ctrl, selection_ctrl):
        super().__init__()
        self.__project = project
        self.__scene_ctrl = scene_ctrl
        self.__selection_ctrl = selection_ctrl
        project.partitions.subscribe(self.__on_partitions_changed)

    def __on_partitions_changed(self, _ids_changed: bool, list_changed: bool):
        if list_changed:
            self.partitionsChanged.emit()

    def __show_project(self, reset_view: bool = True):
        """Rebuild the scene from the project. reset_view: a new file was
        opened (QML recreates its view toggles then)."""
        p = self.__project
        if reset_view:
            self.__scene_ctrl.reset_view_toggles()
        self.__scene_ctrl.add_surface_geometry(p.surface.vertices, p.surface.triangles)
        self.__selection_ctrl.set_picking_enabled(True)
        self.__selection_ctrl.load_geometry(p.surface.vertices, p.surface.triangles)
        if p.volume is not None:
            if p.volume.has_tetrahedra:
                self.__scene_ctrl.add_volume_unstructured_mesh(p.volume.vertices, p.volume.tetrahedra)
            else:
                self.__scene_ctrl.add_volume_geometry(p.volume.vertices, p.volume.triangles)
        self.sessionChanged.emit()

    # --- opening files / meshing result ------------------------------------

    @Slot(str, float)
    @Slot(str)
    def loadSurface(self, file_path: str, scale: float = 1.0):
        project_ops.open_surface(self.__project, file_path, scale)
        self.__show_project()

    @Slot(str)
    def loadVolume(self, file_path: str):
        project_ops.open_volume(self.__project, file_path)
        self.__show_project()

    def loadProject(self, file_path: str) -> str:
        """Replace the project with a .pvp file. Returns "" or an error message."""
        try:
            project_ops.open_project_file(self.__project, file_path)
        except Exception as e:
            print(f"loadProject failed: {e}")
            return str(e)
        self.__show_project()
        print(f"Loaded project {file_path}")
        return ""

    def take_mesh_result(self, result, boundaries: BoundarySnapshot | None):
        """Called by MeshingCtrl when a mesher finished."""
        project_ops.take_mesh_result(self.__project, result.vertices, result.triangles,
                                     result.tetrahedra, "meshed", boundaries)
        self.__show_project(reset_view=False)

    @Slot()
    def createBackgroundMesh(self):
        if self.__project.surface is None:
            return
        project_ops.add_bounding_box(self.__project)
        self.__scene_ctrl.add_background_geometry(self.__project.background)
        self.sessionChanged.emit()

    # --- project file ------------------------------------------------------

    @Slot(result=bool)
    def canSaveProject(self) -> bool:
        return self.__project.surface is not None

    @Slot(str, result=str)
    def saveProject(self, file_path: str) -> str:
        """Write the whole project to a .pvp file. Returns "" or an error message."""
        if not self.canSaveProject():
            return "Nothing to save: no geometry loaded."
        try:
            file_path = project_ops.save_project_file(self.__project, _local_path(file_path))
        except Exception as e:
            print(f"saveProject failed: {e}")
            return str(e)
        print(f"Saved project {file_path}")
        return ""

    # --- partitions --------------------------------------------------------

    @Slot()
    def undo(self):
        self.__project.partitions.undo()

    @Slot()
    def redo(self):
        self.__project.partitions.redo()

    @Slot(bool)
    def setPickingEnabled(self, enabled: bool):
        self.__selection_ctrl.set_picking_enabled(enabled)

    @Slot(str, result=int)
    def createPartition(self, name: str) -> int:
        if self.__project.surface is None or not name.strip():
            return -1
        return self.__project.partitions.add(name.strip())

    @Slot(int)
    def deletePartition(self, pid: int):
        self.__project.partitions.delete(pid)

    @Slot(int)
    def selectPartition(self, pid: int):
        self.__project.partitions.set_current(pid if pid > 0 else None)

    @Slot(result='QVariantList')
    def getPartitions(self) -> list:
        parts = self.__project.partitions
        current = parts.current_id()
        return [{
            "id": p.id,
            "name": p.name,
            "color": "#{:02x}{:02x}{:02x}".format(*(int(c * 255) for c in p.color)),
            "selected": p.id == current,
        } for p in parts.all()]

    # --- export ------------------------------------------------------------

    @Slot(result=bool)
    def canExportVolume(self) -> bool:
        return self.__project.can_export_volume()

    @Slot(result='QVariantMap')
    def getExportSummary(self) -> dict:
        return export.export_summary(self.__project)

    @Slot(result='QVariantList')
    def getExportFormats(self) -> list:
        """List exposed in the export dialog; QML drives the picker from it."""
        return [{"key": f.key, "label": f.label, "ext": f.ext, "quadratic": f.quadratic}
                for f in EXPORT_FORMATS.values()]

    @Slot(str, result=str)
    @Slot(str, str, bool, result=str)
    def exportVolume(self, file_path: str, format_key: str = "vol",
                     quadratic: bool = False) -> str:
        """Write the volume mesh incl. boundary-condition labels in the chosen
        format. Returns "" on success, otherwise an error message for the UI."""
        try:
            path, mesh = export.export_volume(self.__project, _local_path(file_path),
                                              format_key, quadratic)
        except Exception as e:
            print(f"exportVolume failed: {e}")
            return str(e)
        print(f"Exported {path} ({format_key}, quadratic={quadratic}): "
              + ", ".join(f"{g.name} ({len(g.triangles)})" for g in mesh.bc_groups))
        return ""

    @Slot(result='QVariantList')
    def getMeshRoles(self) -> list:
        p = self.__project
        return [{"role": role, "name": name if mesh is not None else "", "loaded": mesh is not None}
                for role, mesh, name in [("surface", p.surface, p.name),
                                         ("volume", p.volume, p.name),
                                         ("background", p.background, "OBB")]]
