import xml.etree.ElementTree as ET

from pvp.visualization.vtk import vtklib as vtk


def create_color_transfer_function_from_xml(xml_text: str, color_steps: int = 32):
    """Color transfer function and a `color_steps`-entry lookup table from a
    ParaView-style colormap XML (<Point x r g b/> entries over [0, 1])."""
    ctf = vtk.vtkColorTransferFunction()
    for point in ET.fromstring(xml_text).iter("Point"):
        ctf.AddRGBPoint(*(float(point.get(k)) for k in ("x", "r", "g", "b")))

    lut = vtk.vtkLookupTable()
    lut.SetNumberOfTableValues(color_steps)
    lut.Build()
    for i in range(color_steps):
        r, g, b = ctf.GetColor(i / (color_steps - 1.0))
        lut.SetTableValue(i, r, g, b, 1.0)

    ctf.SetVectorModeToMagnitude()
    lut.SetVectorModeToMagnitude()
    return ctf, lut
