"""File formats pvp reads and writes: the one place that maps extensions to
what they contain and lists the export writers."""
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from pvp.fileio.NetgenVolWriter import write_vol
from pvp.fileio.MshWriter import write_msh_v2, write_msh_v4
from pvp.fileio.InpWriter import write_inp_calculix, write_inp_abaqus

SURFACE_EXTS = (".stl", ".obj")     # triangle surface, no units
VOLUME_EXTS  = (".vol", ".msh")     # tet mesh, possibly with boundary conditions
RESULT_EXTS  = (".vtk",)            # surface with point fields
PROJECT_EXT  = ".pvp"


def file_kind(path: str) -> str:
    """"surface", "volume", "result", "project" or "" for unknown files."""
    ext = Path(path).suffix.lower()
    if ext in SURFACE_EXTS:
        return "surface"
    if ext in VOLUME_EXTS:
        return "volume"
    if ext in RESULT_EXTS:
        return "result"
    if ext == PROJECT_EXT:
        return "project"
    return ""


@dataclass(frozen=True)
class ExportFormat:
    key: str
    label: str
    ext: str
    writer: Callable
    quadratic: bool     # writer takes quadratic= (Tet10 output)


EXPORT_FORMATS = {f.key: f for f in [
    ExportFormat("vol",          "Netgen volume mesh (.vol)", ".vol", write_vol,          False),
    ExportFormat("msh2",         "Gmsh mesh v2 ASCII (.msh)", ".msh", write_msh_v2,       True),
    ExportFormat("msh4",         "Gmsh mesh v4 ASCII (.msh)", ".msh", write_msh_v4,       True),
    ExportFormat("inp_calculix", "CalculiX (.inp)",           ".inp", write_inp_calculix, True),
    ExportFormat("inp_abaqus",   "Abaqus (.inp)",             ".inp", write_inp_abaqus,   True),
]}
