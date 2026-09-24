"""Calculate ground point density for each survey within AOI
Also extracts raw gps time range for each survey within AOI
"""


import json
import tempfile

from pathlib import Path

from .pdal_runner import run_pipeline
from .crs_utils import reproject_polygon_wkt
from .las_metadata import read_las_header


def ground_point_stats(
    las_file,
    crop_polygon=None,
    env=None
):
    """Calculates number of ground-classified points and GPS time range
    for a LAS/LAZ file, optionally cropped to crop_polygon.

    gps_time_range is the (minimum, maximum) GpsTime scalar field
    still in whatever time base the file uses
    """

    # Check to see what format the las file is in to see if GPS time field exists
    # (format 0 and 2 do not contain this field)
    has_gps_time = (
        read_las_header(las_file, env=env).get("dataformat_id") not in (0, 2)
    )

    # Generate pipeline to filter by ground classification
    pipeline = [
        str(las_file),
        {
            "type": "filters.range",
            "limits": "Classification[2:2]"
        }
    ]

    # Append pipeline with crop if crop_polygon exists
    if crop_polygon:

        pipeline.append(
            {
                "type": "filters.crop",
                "polygon": crop_polygon
            }
        )

    # Append pipeline to get GPS time stats
    pipeline.append(
        {
            "type": "filters.stats",
            "dimensions": "X,GpsTime" if has_gps_time else "X"
        }
    )

    # Don't write output
    pipeline.append(
        {
            "type": "writers.null"
        }
    )

    # Run the above PDAL pipeline and organize outputs
    with tempfile.TemporaryDirectory() as tmp_dir:

        pipeline_path = Path(tmp_dir) / "count_pipeline.json"
        metadata_path = Path(tmp_dir) / "count_metadata.json"

        run_pipeline(
            pipeline,
            pipeline_path,
            env=env,
            metadata_path=metadata_path
        )

        with open(metadata_path) as f:

            stats = json.load(f)["stages"]["filters.stats"]

    statistic = stats.get("statistic", [])

    if isinstance(statistic, dict):

        statistic = [statistic]

    by_dimension = {entry["name"]: entry for entry in statistic}

    count = int(by_dimension["X"]["count"]) if "X" in by_dimension else 0

    gps_time = by_dimension.get("GpsTime")

    # With no points left, filters.stats still reports a GpsTime entry, but
    # its minimum/maximum are placeholders rather than real times.
    gps_time_range = (
        (gps_time["minimum"], gps_time["maximum"])
        if gps_time and count
        else None
    )

    return count, gps_time_range


def estimate_ground_point_density(
    files,
    aoi_wkt,
    aoi_srs_wkt,
    aoi_area_m2,
    dataset_crs,
    env=None
):
    """Estimate ground-classified point density by summing points
    across all LAS/LAZ files cropped to the AOI extent.

    Returns (total_points, points_per_m2, gps_time_range), with aoi_area_m2
    as the density denominator, and gps_time_range the raw (minimum,
    maximum) GpsTime spanned by those same points across every file
    """

    # Reproject the crop polygon to crs with linear meter units
    crop_polygon = reproject_polygon_wkt(
        aoi_wkt,
        aoi_srs_wkt,
        dataset_crs
    )

    files = list(files)

    total_points = 0
    earliest = None
    latest = None

    # Loop through all LAS/LAZ files to calculate total number of points
    for i, file in enumerate(files, start=1):

        count, gps_time_range = ground_point_stats(
            file,
            crop_polygon=crop_polygon,
            env=env
        )

        total_points += count

        if gps_time_range:

            minimum, maximum = gps_time_range

            earliest = minimum if earliest is None else min(earliest, minimum)
            latest = maximum if latest is None else max(latest, maximum)

        print(
            f"[{i}/{len(files)}] {file.name}: "
            f"{count:,} ground points in AOI"
        )

    # Calculate point density
    density = (
        total_points / aoi_area_m2
        if aoi_area_m2 else 0.0
    )

    gps_time_range = (
        (earliest, latest) if earliest is not None else None
    )

    return total_points, density, gps_time_range
