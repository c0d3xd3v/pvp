from abc import ABC, abstractmethod


class AbstractGeometryData(ABC):
    @abstractmethod
    def get_vertices(self): ...

    @abstractmethod
    def get_triangles(self): ...


class AbstractResultData(ABC):
    @abstractmethod
    def get_vertices(self): ...

    @abstractmethod
    def get_triangles(self): ...

    @abstractmethod
    def get_field_names(self): ...

    @abstractmethod
    def get_vertex_field_data(self, field_name: str): ...
