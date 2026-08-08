# Planned Selection Modes

`SelectionCtrl` currently uses BFS-based face selection. The architecture is intended to support multiple interchangeable selection modes (Strategy Pattern via `AbstractSelectionMode`).

## Implemented

- **BFS / Normal-based** — click a face, region grows across connected faces within a normal-angle threshold

## Planned

- **Box Select** — user spans a bounding box in 3D space; all faces/points inside are selected
- **Sphere Select** — user picks a center point and radius; all faces/points within the sphere are selected
- **Lasso** — freehand screen-space selection; projects to 3D to determine included faces/points
- **External Geometry Select** — arbitrary helper geometry (imported mesh) used as selection volume
