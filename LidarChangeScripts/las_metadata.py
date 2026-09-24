"""LAS/LAZ metadata tools. Reads headers, CRS, point count,
and compares extent with AOI polygon.
"""

import json

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from osgeo import ogr

from .pdal_runner import run_pdal
from .crs_utils import reproject_polygon_wkt


_HEADER_CACHE = {}


def read_las_header(
    las_file,
    env=None
):
    """Reads and caches LAS/LAZ file header metadata
    (bounds, point count, CRS, ...), via `pdal info --metadata`.
    """

    las_file = Path(las_file)
    stat = las_file.stat()
    key = (str(las_file.resolve()), stat.st_mtime_ns, stat.st_size)

    if key not in _HEADER_CACHE:

        result = run_pdal(
            [
                "info",
                "--metadata",
                las_file
            ],
            env=env
        )

        _HEADER_CACHE[key] = json.loads(result.stdout).get("metadata", {})

    return _HEADER_CACHE[key]


def _epsg_id(crs_json):
    """Extract the EPSG code from a projjson CRS object.
    """

    crs_json = crs_json.get("source_crs", crs_json)
    crs_id = crs_json.get("id", {})

    if crs_id.get("authority") == "EPSG" and "code" in crs_id:

        return f"EPSG:{crs_id['code']}"

    return None


def read_las_crs(
    las_file,
    env=None
):
    """Extract the crs and horizontal_crs recorded in the LAS/LAZ file header."""

    srs_json = (
        read_las_header(las_file, env=env)
        .get("srs", {})
        .get("json", {})
    )

    crs_type = srs_json.get("type")

    if crs_type == "CompoundCRS":

        horizontal = None
        vertical = None

        for component in srs_json.get("components", []):

            # Either part may be wrapped in a BoundCRS; its source_crs says
            # which part it is.
            component_type = component.get("source_crs", component).get("type")

            if component_type == "VerticalCRS":

                vertical = _epsg_id(component)

            else:

                horizontal = _epsg_id(component)

        if horizontal and vertical:

            return f"{horizontal}+{vertical.split(':')[1]}", horizontal

        return None, horizontal

    if crs_type in ("ProjectedCRS", "BoundCRS", "GeographicCRS"):

        return None, _epsg_id(srs_json)

    return None, None


def get_dataset_crs(
    las_files,
    label,
    env=None,
    max_workers=8
):
    """Extract CRS shared by every file in one epoch's dataset and
    check for agreement.
    """

    las_files = list(las_files)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:

        crs_info = list(
            pool.map(lambda f: read_las_crs(f, env=env), las_files)
        )

    files_by_crs = defaultdict(list)

    for las_file, (crs, horizontal) in zip(las_files, crs_info):

        key = crs or (f"{horizontal} (horizontal only)" if horizontal else "none recorded")
        files_by_crs[key].append(Path(las_file).name)

    details = "\n".join(
        f"  {key}: {len(names)} file(s), e.g. {names[0]}"
        for key, names in sorted(files_by_crs.items())
    )

    compounds = sorted({crs for crs, _ in crs_info if crs})
    horizontals = sorted({horizontal for _, horizontal in crs_info if horizontal})

    if len(compounds) > 1 or len(horizontals) > 1:

        raise ValueError(
            f"The {label} files don't all share one CRS:\n{details}\n"
            f"Reproject them to a common CRS first."
        )

    if compounds:

        crs = compounds[0]
        incomplete = len(las_files) - len(files_by_crs[crs])

        if incomplete:

            print(
                f"WARNING: {incomplete} of {len(las_files)} {label} file(s) "
                f"don't record a full compound CRS; assuming they match the "
                f"rest ({crs}). CRSs found:\n{details}"
            )

        return crs, None

    return None, (horizontals[0] if horizontals else None)


def files_overlapping_polygon(
    las_files,
    polygon_wkt,
    polygon_crs,
    dataset_crs,
    label,
    env=None,
    max_workers=8
):
    """The subset of las_files whose header bounding box intersects
    polygon_wkt (given in polygon_crs)
    """

    las_files = list(las_files)

    polygon = ogr.CreateGeometryFromWkt(
        reproject_polygon_wkt(polygon_wkt, polygon_crs, dataset_crs)
    )

    with ThreadPoolExecutor(max_workers=max_workers) as pool:

        headers = list(
            pool.map(lambda f: read_las_header(f, env=env), las_files)
        )

    overlapping = []

    for las_file, header in zip(las_files, headers):

        ring = ogr.Geometry(ogr.wkbLinearRing)
        ring.AddPoint_2D(header["minx"], header["miny"])
        ring.AddPoint_2D(header["maxx"], header["miny"])
        ring.AddPoint_2D(header["maxx"], header["maxy"])
        ring.AddPoint_2D(header["minx"], header["maxy"])
        ring.AddPoint_2D(header["minx"], header["miny"])

        file_box = ogr.Geometry(ogr.wkbPolygon)
        file_box.AddGeometry(ring)

        if file_box.Intersects(polygon):

            overlapping.append(las_file)

    skipped = len(las_files) - len(overlapping)

    print(
        f"{label}: {len(overlapping)} of {len(las_files)} file(s) overlap "
        f"the AOI"
        + (f" -- skipping the other {skipped}" if skipped else "")
    )

    if not overlapping:

        raise RuntimeError(
            f"None of the {label} files overlap the AOI. Check that the AOI "
            f"shapefile covers the data, and that the {label} CRS "
            f"({dataset_crs}) is right."
        )

    return overlapping


def get_point_count(
    las_file,
    env=None
):
    """Total point count of a LAS/LAZ file, via `pdal info --summary`."""

    result = run_pdal(
        [
            "info",
            "--summary",
            las_file
        ],
        env=env
    )

    return json.loads(result.stdout)["summary"]["num_points"]
