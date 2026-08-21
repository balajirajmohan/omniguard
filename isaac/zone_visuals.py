"""Polished, non-colliding USD overlays for OmniGuard's warehouse zones.

The layout functions in this module intentionally have no Isaac/pxr imports, so
their coordinate math can be tested on a laptop. ``add_zone_visuals`` imports pxr
only when called inside a running Isaac Sim application.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Iterable, Mapping, Sequence

Color = tuple[float, float, float]
Point = tuple[float, float]
Polygon = tuple[Point, ...]
Rect = Mapping[str, float]

# Exact sRGB colours used by ui-controller/src/index.css.
SAFE_FILL: Color = (5 / 255, 150 / 255, 105 / 255)       # --color-ok-solid
SAFE_ACCENT: Color = (52 / 255, 211 / 255, 153 / 255)   # --color-ok
RESTRICTED_FILL: Color = (220 / 255, 38 / 255, 38 / 255)  # --color-bad-solid
RESTRICTED_ACCENT: Color = (248 / 255, 113 / 255, 113 / 255)  # --color-bad
WAYPOINT_ACCENT: Color = (96 / 255, 165 / 255, 250 / 255)  # --color-info

ROOT_PATH = "/World/OmniGuardZones"


@dataclass(frozen=True)
class ZoneLayout:
    """Renderer-neutral description of one warehouse zone."""

    name: str
    label: str
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    waypoint: Point
    restricted: bool
    fill_color: Color
    accent_color: Color

    @property
    def width(self) -> float:
        return self.x_max - self.x_min

    @property
    def height(self) -> float:
        return self.y_max - self.y_min


def _human_label(name: str) -> str:
    return name.replace("_", " ")


def build_zone_layouts(
    zones: Mapping[str, Rect],
    waypoints: Mapping[str, Point],
) -> tuple[ZoneLayout, ...]:
    """Build deterministic visuals from the same rectangles served to the UI."""

    layouts: list[ZoneLayout] = []
    for name, rect in zones.items():
        restricted = "RESTRICTED" in name.upper() or "HUMAN" in name.upper()
        x_min, x_max = float(rect["x_min"]), float(rect["x_max"])
        y_min, y_max = float(rect["y_min"]), float(rect["y_max"])
        if x_min >= x_max or y_min >= y_max:
            raise ValueError(f"Zone {name!r} must have positive width and height")

        fallback = ((x_min + x_max) / 2, (y_min + y_max) / 2)
        waypoint = tuple(map(float, waypoints.get(name, fallback)))
        layouts.append(
            ZoneLayout(
                name=name,
                label=_human_label(name),
                x_min=x_min,
                x_max=x_max,
                y_min=y_min,
                y_max=y_max,
                waypoint=(waypoint[0], waypoint[1]),
                restricted=restricted,
                fill_color=RESTRICTED_FILL if restricted else SAFE_FILL,
                accent_color=RESTRICTED_ACCENT if restricted else SAFE_ACCENT,
            )
        )
    return tuple(layouts)


def rectangle_polygon(x_min: float, x_max: float, y_min: float, y_max: float) -> Polygon:
    return ((x_min, y_min), (x_max, y_min), (x_max, y_max), (x_min, y_max))


def border_polygons(layout: ZoneLayout, width: float = 0.09) -> tuple[Polygon, ...]:
    """Return four inward-facing border strips for a zone."""

    w = min(width, layout.width / 2, layout.height / 2)
    return (
        rectangle_polygon(layout.x_min, layout.x_max, layout.y_min, layout.y_min + w),
        rectangle_polygon(layout.x_min, layout.x_max, layout.y_max - w, layout.y_max),
        rectangle_polygon(layout.x_min, layout.x_min + w, layout.y_min + w, layout.y_max - w),
        rectangle_polygon(layout.x_max - w, layout.x_max, layout.y_min + w, layout.y_max - w),
    )


def _clip_polygon_to_rect(polygon: Sequence[Point], layout: ZoneLayout) -> Polygon:
    """Sutherland-Hodgman clip used to keep hazard bands inside their zone."""

    def clip(
        points: Sequence[Point],
        inside,
        intersect,
    ) -> list[Point]:
        if not points:
            return []
        output: list[Point] = []
        previous = points[-1]
        previous_inside = inside(previous)
        for current in points:
            current_inside = inside(current)
            if current_inside != previous_inside:
                output.append(intersect(previous, current))
            if current_inside:
                output.append(current)
            previous, previous_inside = current, current_inside
        return output

    def at_x(a: Point, b: Point, x: float) -> Point:
        t = (x - a[0]) / (b[0] - a[0])
        return (x, a[1] + t * (b[1] - a[1]))

    def at_y(a: Point, b: Point, y: float) -> Point:
        t = (y - a[1]) / (b[1] - a[1])
        return (a[0] + t * (b[0] - a[0]), y)

    result: Sequence[Point] = polygon
    result = clip(result, lambda p: p[0] >= layout.x_min, lambda a, b: at_x(a, b, layout.x_min))
    result = clip(result, lambda p: p[0] <= layout.x_max, lambda a, b: at_x(a, b, layout.x_max))
    result = clip(result, lambda p: p[1] >= layout.y_min, lambda a, b: at_y(a, b, layout.y_min))
    result = clip(result, lambda p: p[1] <= layout.y_max, lambda a, b: at_y(a, b, layout.y_max))
    return tuple(result)


def hazard_stripe_polygons(
    layout: ZoneLayout,
    *,
    spacing: float = 1.15,
    width: float = 0.22,
) -> tuple[Polygon, ...]:
    """Create clipped 45-degree bands matching the UI's restricted hatch."""

    if not layout.restricted:
        return ()
    cx = (layout.x_min + layout.x_max) / 2
    cy = (layout.y_min + layout.y_max) / 2
    half_length = math.hypot(layout.width, layout.height)
    along = (math.sqrt(0.5), math.sqrt(0.5))
    normal = (-along[1], along[0])
    sweep = half_length
    count = math.ceil((2 * sweep) / spacing)
    stripes: list[Polygon] = []

    for index in range(count + 1):
        offset = -sweep + index * spacing
        center = (cx + normal[0] * offset, cy + normal[1] * offset)
        corners = (
            (center[0] - along[0] * half_length - normal[0] * width / 2,
             center[1] - along[1] * half_length - normal[1] * width / 2),
            (center[0] + along[0] * half_length - normal[0] * width / 2,
             center[1] + along[1] * half_length - normal[1] * width / 2),
            (center[0] + along[0] * half_length + normal[0] * width / 2,
             center[1] + along[1] * half_length + normal[1] * width / 2),
            (center[0] - along[0] * half_length + normal[0] * width / 2,
             center[1] - along[1] * half_length + normal[1] * width / 2),
        )
        clipped = _clip_polygon_to_rect(corners, layout)
        if len(clipped) >= 3:
            stripes.append(clipped)
    return tuple(stripes)


# Compact 5x7 font. Only glyphs needed by the three zone labels are included.
_FONT: dict[str, tuple[str, ...]] = {
    " ": ("00000",) * 7,
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "N": ("10001", "11001", "11001", "10101", "10011", "10011", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
}


def label_polygons(layout: ZoneLayout) -> tuple[Polygon, ...]:
    """Return readable bitmap lettering near the top-left of the floor area."""

    text = layout.label.upper()
    missing = set(text) - _FONT.keys()
    if missing:
        raise ValueError(f"Unsupported zone-label characters: {sorted(missing)!r}")

    units_wide = max(1, len(text) * 6 - 1)
    pixel = min(0.14, layout.width * 0.86 / units_wide, layout.height * 0.16)
    origin_x = layout.x_min + layout.width * 0.07
    origin_y = layout.y_max - layout.height * 0.08
    cells: list[Polygon] = []
    for char_index, char in enumerate(text):
        for row, bits in enumerate(_FONT[char]):
            for column, bit in enumerate(bits):
                if bit != "1":
                    continue
                x0 = origin_x + (char_index * 6 + column) * pixel
                y1 = origin_y - row * pixel
                cells.append(rectangle_polygon(x0, x0 + pixel * 0.82, y1 - pixel * 0.82, y1))
    return tuple(cells)


def ring_polygons(
    center: Point,
    *,
    radius: float = 0.28,
    width: float = 0.055,
    segments: int = 24,
) -> tuple[Polygon, ...]:
    """Create a slim floor ring for a command destination waypoint."""

    inner = radius - width
    rings: list[Polygon] = []
    for i in range(segments):
        a0 = 2 * math.pi * i / segments
        a1 = 2 * math.pi * (i + 1) / segments
        rings.append(
            (
                (center[0] + inner * math.cos(a0), center[1] + inner * math.sin(a0)),
                (center[0] + radius * math.cos(a0), center[1] + radius * math.sin(a0)),
                (center[0] + radius * math.cos(a1), center[1] + radius * math.sin(a1)),
                (center[0] + inner * math.cos(a1), center[1] + inner * math.sin(a1)),
            )
        )
    return tuple(rings)


def _safe_prim_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", value)


def add_zone_visuals(
    stage,
    zones: Mapping[str, Rect],
    waypoints: Mapping[str, Point],
    *,
    root_path: str = ROOT_PATH,
    floor_z: float = 0.025,
) -> tuple[ZoneLayout, ...]:
    """Author all zone overlays beneath ``root_path`` on an Isaac USD stage.

    The generated meshes have no collision or rigid-body schemas. Restricted
    visuals sit a few millimetres above safe visuals so the policy's
    "restricted wins" overlap rule is visible and z-fighting is avoided.
    """

    from pxr import Gf, Sdf, UsdGeom, UsdShade  # type: ignore

    layouts = build_zone_layouts(zones, waypoints)
    if stage.GetPrimAtPath(root_path):
        stage.RemovePrim(root_path)
    UsdGeom.Xform.Define(stage, root_path)
    materials_path = f"{root_path}/Materials"
    UsdGeom.Scope.Define(stage, materials_path)

    def material(name: str, color: Color, opacity: float, emissive: float = 0.0):
        path = f"{materials_path}/{name}"
        mat = UsdShade.Material.Define(stage, path)
        shader = UsdShade.Shader.Define(stage, f"{path}/PreviewSurface")
        shader.CreateIdAttr("UsdPreviewSurface")
        shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
        shader.CreateInput("opacity", Sdf.ValueTypeNames.Float).Set(opacity)
        shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.58)
        if emissive:
            shader.CreateInput("emissiveColor", Sdf.ValueTypeNames.Color3f).Set(
                Gf.Vec3f(*(channel * emissive for channel in color))
            )
        mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
        return mat

    materials = {
        "safe_fill": material("SafeFill", SAFE_FILL, 0.20),
        "safe_accent": material("SafeAccent", SAFE_ACCENT, 0.94, 0.28),
        "restricted_fill": material("RestrictedFill", RESTRICTED_FILL, 0.22),
        "restricted_accent": material("RestrictedAccent", RESTRICTED_ACCENT, 0.95, 0.30),
        "waypoint": material("Waypoint", WAYPOINT_ACCENT, 0.96, 0.32),
    }

    def mesh(path: str, polygons: Iterable[Polygon], z: float, mat) -> None:
        polygon_list = [polygon for polygon in polygons if len(polygon) >= 3]
        points = []
        counts = []
        indices = []
        for polygon in polygon_list:
            start = len(points)
            points.extend(Gf.Vec3f(x, y, z) for x, y in polygon)
            counts.append(len(polygon))
            indices.extend(range(start, start + len(polygon)))
        usd_mesh = UsdGeom.Mesh.Define(stage, path)
        usd_mesh.CreatePointsAttr(points)
        usd_mesh.CreateFaceVertexCountsAttr(counts)
        usd_mesh.CreateFaceVertexIndicesAttr(indices)
        usd_mesh.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
        UsdShade.MaterialBindingAPI(usd_mesh.GetPrim()).Bind(mat)

    for layout in layouts:
        prim_name = _safe_prim_name(layout.name)
        zone_path = f"{root_path}/{prim_name}"
        UsdGeom.Xform.Define(stage, zone_path)
        restricted_lift = 0.008 if layout.restricted else 0.0
        base_z = floor_z + restricted_lift
        fill_material = materials["restricted_fill" if layout.restricted else "safe_fill"]
        accent_material = materials["restricted_accent" if layout.restricted else "safe_accent"]

        mesh(
            f"{zone_path}/FloorTint",
            [rectangle_polygon(layout.x_min, layout.x_max, layout.y_min, layout.y_max)],
            base_z,
            fill_material,
        )
        mesh(f"{zone_path}/Border", border_polygons(layout), base_z + 0.003, accent_material)
        if layout.restricted:
            mesh(
                f"{zone_path}/HazardStripes",
                hazard_stripe_polygons(layout),
                base_z + 0.004,
                accent_material,
            )
        mesh(f"{zone_path}/Label", label_polygons(layout), base_z + 0.006, accent_material)
        mesh(
            f"{zone_path}/Waypoint",
            ring_polygons(layout.waypoint),
            base_z + 0.007,
            materials["waypoint"],
        )

    return layouts