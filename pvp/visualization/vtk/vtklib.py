"""The VTK modules pvp uses, as one namespace: `from pvp.visualization.vtk import vtklib as vtk`.

`import vtk` loads all ~180 VTK modules (~0.7 s at startup); these are the ~20
we need (~0.3 s). Some are imported only for their object-factory overrides
and are never referenced by name — dropping them breaks rendering at runtime,
not at import time:
  vtkRenderingOpenGL2      OpenGL implementations of mappers, render window, ...
  vtkRenderingFreeType     text rendering (orientation gizmo axis labels)
  vtkInteractionStyle      default interactor styles
"""
from vtkmodules.vtkCommonCore import *            # noqa: F401,F403
from vtkmodules.vtkCommonDataModel import *       # noqa: F401,F403
from vtkmodules.vtkCommonExecutionModel import *  # noqa: F401,F403
from vtkmodules.vtkCommonColor import *           # noqa: F401,F403
from vtkmodules.vtkFiltersCore import *           # noqa: F401,F403
from vtkmodules.vtkFiltersExtraction import *     # noqa: F401,F403
from vtkmodules.vtkFiltersGeneral import *        # noqa: F401,F403
from vtkmodules.vtkFiltersGeometry import *       # noqa: F401,F403
from vtkmodules.vtkFiltersProgrammable import *   # noqa: F401,F403
from vtkmodules.vtkIOImage import *               # noqa: F401,F403
from vtkmodules.vtkIOLegacy import *              # noqa: F401,F403
from vtkmodules.vtkIOXML import *                 # noqa: F401,F403
from vtkmodules.vtkImagingCore import *           # noqa: F401,F403
from vtkmodules.vtkInteractionStyle import *      # noqa: F401,F403
from vtkmodules.vtkInteractionWidgets import *    # noqa: F401,F403
from vtkmodules.vtkRenderingAnnotation import *   # noqa: F401,F403
from vtkmodules.vtkRenderingCore import *         # noqa: F401,F403
from vtkmodules.vtkRenderingFreeType import *     # noqa: F401,F403
from vtkmodules.vtkRenderingOpenGL2 import *      # noqa: F401,F403
from vtkmodules.vtkRenderingUI import *           # noqa: F401,F403
