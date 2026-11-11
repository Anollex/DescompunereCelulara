# Map Builder

Start the application with `python main.py` and open the **Map Builder** tab.
The builder is drawn inside the main window and follows its size and theme.

## Placing shapes

- **Rectangle, Triangle, Circle / Oval**: click the shape in the palette and then
  click on the canvas, or drag it from the palette onto the canvas. A blue outline
  shows where it will land.
- **Custom shape**: click it in the palette, then draw on the canvas:
  - click to add points one by one, or hold the mouse button and drag to draw freehand;
  - close the shape with Enter, a right click, a click on the first point or a double click;
  - Backspace removes the last point, Esc cancels.

## Changing a shape

Click a shape to select it, drag it to move it.

| Handle | Effect |
|---|---|
| filled square (corner) | resize, keeping the proportions; hold Shift to resize freely |
| hollow square (side) | stretch along one direction; this turns a circle into an oval |
| round handle above the shape | rotate; hold Shift to snap to 15 degrees |

The opposite corner or side stays in place while you drag.

**Editing points** (triangles and custom shapes): double-click the shape or press
**Edit points** in the Properties panel. Drag an orange point to move it. A new
triangle is equilateral, so this is how you turn it into any other triangle. For
custom shapes you can also drag one of the small markers on an edge to add a point
there, and right-click a point to remove it. Press **Done** or Esc to finish.

The Properties panel shows and edits the position (top-left corner of the bounding
box), the angle and the size. Click a value, type a new one and press Enter.
**Locked / Unlocked** protects a shape from changes. **Delete** or the Delete key
removes it.

## Saving

**Save Map** asks for a name and writes the map into `maps/`. Existing files are
never overwritten; a numeric suffix is added when needed. The new map becomes the
selected map in the simulation tabs. **Clear** (click twice) empties the canvas.

Saved maps use a `1000 x 1000` SVG viewBox and contain one `<polygon>` per shape.

## Tests

`python -m pytest MapBuilder/test_map_builder.py` checks the shape model: stretching,
corner resizing, vertex editing, custom polygons and the SVG round trip.
