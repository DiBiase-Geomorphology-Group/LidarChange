"""Naming conventions for tiling steps: "{prefix}{llx}_{lly}.las"
where (llx, lly) is the lower-left corner of the tile cell.
"""

import re

from pathlib import Path

from osgeo import ogr


def tile_paths(
    tiles_dir,
    prefix
):
    """Generate list of tile files for one epoch.
    """

    tiles_dir = Path(tiles_dir)

    return sorted(
        list(tiles_dir.glob(f"{prefix}*.las"))
        +
        list(tiles_dir.glob(f"{prefix}*.laz"))
    )


def parse_tile_origin(
    tile_path,
    prefix
):
    """Extract a retiled tile's (llx, lly) grid origin from its filename,
    as written by retile_clouds: "{prefix}{llx}_{lly}.las" (or .laz).
    For a tile produced by merge_partial_tiles, (llx, lly) is the origin
    of the largest merged member.
    """

    match = re.match(
        rf"{re.escape(prefix)}(-?\d+)_(-?\d+)(?:_merged)?\.la[sz]$",
        Path(tile_path).name
    )

    if not match:

        raise ValueError(
            f"Filename doesn't match "
            f"'{prefix}<llx>_<lly>[_merged].las/.laz': {tile_path}"
        )

    return int(match.group(1)), int(match.group(2))


def cells_union_wkt(
    cells,
    tile_size
):
    """WKT polygon for the union of one or more tile_size x tile_size grid
    cells, each given as its (llx, lly) origin. A merged tile can cover a
    non-rectangular run of cells (e.g. an L-shaped cluster at an AOI
    corner), so this is the exact footprint, not just its bounding box.
    """

    union = None

    for llx, lly in cells:

        ring = ogr.Geometry(ogr.wkbLinearRing)
        ring.AddPoint(llx, lly)
        ring.AddPoint(llx + tile_size, lly)
        ring.AddPoint(llx + tile_size, lly + tile_size)
        ring.AddPoint(llx, lly + tile_size)
        ring.AddPoint(llx, lly)

        cell_polygon = ogr.Geometry(ogr.wkbPolygon)
        cell_polygon.AddGeometry(ring)

        union = (
            cell_polygon if union is None
            else union.Union(cell_polygon)
        )

    return union.ExportToWkt()
