# Map Builder

Start the application with `python main.py`, then press **Map Builder** in the
simulation window. The builder opens as a separate maximized window.

- Drag Rectangle, Triangle, or Circle from the left palette onto the canvas.
- Click an obstacle to select it; drag it to move it.
- Drag a blue corner handle to resize the selected obstacle proportionally.
- Drag the blue circular handle above the selection to rotate it. Rotation changes
  only the angle, so it does not skew the obstacle.
- **Lock** prevents moving, scaling, or rotating the selected obstacle.
- **Delete** in the Properties panel or the Delete key removes the selected
  obstacle.
- **Save Map** opens a name dialog and writes a compatible map into `../maps`.
  Existing names are not overwritten; a numeric suffix is added when needed.

The Properties panel shows lock state, transformed top-left position, angle, and
shape-specific dimensions. Saved maps use a stable `1000 x 1000` SVG viewBox and are automatically added to
the simulation map list after saving. Select them with the simulation window's
map button.
