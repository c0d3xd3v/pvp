from dataclasses import dataclass


@dataclass
class Partition:
    id: int
    name: str
    color: tuple[float, float, float]
