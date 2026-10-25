from abc import ABC, abstractmethod


class AbstractGeometryData(ABC):
    """Mesh geometry as used by the pre-processing session.

    Arrays are array-like (numpy arrays or nested lists), indices are 0-based.
    Surface-only meshes implement just vertices and triangles; volume meshes
    also provide tetrahedra, and files that carry boundary conditions provide
    the per-triangle BC numbers and their names.
    """

    @abstractmethod
    def get_vertices(self):
        """(N, 3) vertex coordinates."""

    @abstractmethod
    def get_triangles(self):
        """(M, 3) surface triangles (for a volume mesh: its boundary)."""

    def get_tetrahedra(self):
        """(K, 4) tetrahedra; empty for surface-only meshes."""
        return []

    def has_tetrahedra(self) -> bool:
        return len(self.get_tetrahedra()) > 0

    def get_triangle_bcs(self):
        """Boundary-condition number (1-based) per triangle, aligned with
        get_triangles(); empty if the mesh carries no BC information."""
        return []

    def get_bc_names(self) -> dict[int, str]:
        """BC number -> name."""
        return {}


class AbstractResultData(ABC):
    @abstractmethod
    def get_vertices(self): ...

    @abstractmethod
    def get_triangles(self): ...

    @abstractmethod
    def get_field_names(self): ...

    @abstractmethod
    def get_vertex_field_data(self, field_name: str): ...
