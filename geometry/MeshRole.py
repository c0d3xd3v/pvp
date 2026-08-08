from enum import Enum


class MeshRole(Enum):
    SURFACE    = "surface"     # Hauptgeometrie, Regionsselektion
    VOLUME     = "volume"      # Tetraeder-Netz (geladen oder aus FTetWild)
    BACKGROUND = "background"  # OBB für FloatTetwild Sizing-Field
