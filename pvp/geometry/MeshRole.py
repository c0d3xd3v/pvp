from enum import Enum


class MeshRole(Enum):
    SURFACE    = "surface"     # main geometry, region selection
    VOLUME     = "volume"      # tet mesh (loaded or from fTetWild)
    BACKGROUND = "background"  # bounding box for fTetWild's sizing field
