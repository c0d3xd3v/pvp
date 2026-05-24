from collections import deque
from typing import List, Optional, Dict, Set, Tuple
import sys
import igl
import numpy as np


class GraphCompareCondition:
    def compare(self, f1: int, f2: int) -> bool:
        raise NotImplementedError("Must be implemented by subclass")

class DefaultGraphCompareCondition(GraphCompareCondition):
    def compare(self, f1: int, f2: int) -> bool:
        return True

class ConditionalGraph:
    def __init__(self, V: int, condition: Optional[GraphCompareCondition] = None):
        self.V = V
        self.adj = [[] for _ in range(V)]
        self.visited = [False] * V
        self.defaultCompareCondition = DefaultGraphCompareCondition()
        self.compareCondition = condition if condition is not None else self.defaultCompareCondition

    def add_edge(self, v: int, w: int):
        self.adj[v].append(w)

    def BFS(self, s: int) -> List[int]:
        ret = []
        queue = deque([s])
        self.visited[s] = True

        while queue:
            k = queue.popleft()
            ret.append(k)

            for adjacent in self.adj[k]:
                if not self.visited[adjacent]:
                    if self.compareCondition.compare(k, adjacent):
                        queue.append(adjacent)
                    self.visited[adjacent] = True

        return ret

    def reset(self):
        self.visited = [False] * self.V

    def connected_components(self) -> List[List[int]]:
        """Findet alle zusammenhängenden Komponenten im Graphen"""
        components = []
        self.reset()

        for v in range(self.V):
            if not self.visited[v]:
                component = self.BFS(v)
                components.append(component)

        return components
