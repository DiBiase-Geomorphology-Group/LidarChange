"""Pipeline for CloudComPy processing of individual point cloud tiles.
Calls out to to other modules through process_tile_pairs function
"""

import shutil
import time

from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path

import cloudComPy as cc

from .alignment import align_tile_pair
from .m3c2_processing import compute_m3c2_change
from .rasterization import rasterize_and_export, merge_rasters
from .tile_buffering import build_buffered_tile
from .swath_profile import save_icp_transforms
from .dem_utils import (
    rasterize_tile_dem,
    clip_raster_to_polygon,
    fill_dem_holes,
    generate_slope_and_hillshade
)


# Per-tile processing stages, in the order they run
TILE_STAGES = ("buffer", "DEM", "load + subsample", "ICP", "M3C2", "export")


@contextmanager
def _timed(timings, stage):
    """Add the seconds spent inside a `with` block to timings[stage]."""
    start = time.perf_counter()
    try:
        yield
    finally:
        timings[stage] += time.perf_counter() - start


def _format_stage_times(timings):
    parts = [f"{stage} {timings[stage]:.1f}s" for stage in TILE_STAGES if stage in timings]
    return " | ".join(parts) + f" | total {sum(timings.values()):.1f}s"


def _print_timing_summary(run_timings, finishing_seconds, tile_count):
    total = sum(run_timings.values()) + finishing_seconds
    print(f"\nTime by stage ({tile_count} tile pair(s)):")
    for stage in TILE_STAGES:
        seconds = run_timings.get(stage, 0.0)
        print(f"  {stage:<22}{seconds:8.1f} s  {100 * seconds / total:5.1f}%")
    print(f"  {'mosaic + DEM finishing':<22}{finishing_seconds:8.1f} s  {100 * finishing_seconds / total:5.1f}%")
    print(f"  {'total':<22}{total:8.1f} s")


def process_tile_pairs(
    before_folder,
    after_folder,
    before_prefix,
    after_prefix,
    tile_size,
    buffer_distance,
    min_spacing,
    vertical_param_file,
    surface_param_file,
    m3c2_mode,
    m3c2_filter,
    output_cloud_dir,
    output_raster_dir,
    merged_raster_path,
    m3c2_raster_resolution,
    before_dem_resolution,
    after_dem_resolution,
    dem_output_dir,
    merged_before_dem_path,
    merged_after_dem_path,
    before_slope_path,
    before_hillshade_path,
    after_slope_path,
    after_hillshade_path,
    crop_polygon,
    icp_min_rms_decrease=1e-5,
    icp_sampling_limit=500000,
    output_crs=None,
    tile_merge_plan=None,
    env=None
):

    # Directory management
    before_folder = Path(before_folder)
    after_folder = Path(after_folder)

    output_cloud_dir = Path(output_cloud_dir)
    output_cloud_dir.mkdir(parents=True, exist_ok=True)

    output_raster_dir = Path(output_raster_dir)
    output_raster_dir.mkdir(parents=True, exist_ok=True)

    dem_output_dir = Path(dem_output_dir)
    dem_output_dir.mkdir(parents=True, exist_ok=True)

    # Buffered tiles and their PDAL pipeline files are per-tile scratch:
    # built once per tile pair, used by both the DEM and M3C2 steps
    # below, then deleted
    buffered_dir = output_raster_dir / "buffered_tiles"
    buffered_dir.mkdir(parents=True, exist_ok=True)

    pipeline_dir = output_raster_dir / "buffered_pipelines"
    pipeline_dir.mkdir(parents=True, exist_ok=True)

    # Initialize outputs
    raster_outputs = []
    before_dem_outputs = []
    after_dem_outputs = []
    icp_transforms = {}

    run_timings = defaultdict(float)

    # Identify BEFORE point cloud tiles
    before_files = sorted(
        [
            f
            for f in before_folder.iterdir()
            if f.suffix.lower() in [".las", ".laz"]
            and f.name.startswith(before_prefix)
        ]
    )

    print(
        f"Found {len(before_files)} before-event tiles"
    )

    if not before_files:

        raise FileNotFoundError(
            f"No '{before_prefix}*.las/.laz' tiles found in {before_folder}. "
            f"Run the retiling cell first."
        )

    unmatched_tiles = []

    for before_file in before_files:

        suffix = before_file.name[
            len(before_prefix):
        ]

        after_file = after_prefix + suffix

        after_path = after_folder / after_file

        if not after_path.exists():

            print(
                f"No matching AFTER tile: "
                f"{after_file}"
            )

            unmatched_tiles.append(before_file.name)

            continue

        tile_timings = defaultdict(float)

        print(
            "\n===================================="
        )

        print(
            f"BEFORE: {before_file.name}"
        )

        print(
            f"AFTER : {after_path.name}"
        )

        print(
            "===================================="
        )

        tile_stub = Path(suffix).stem

        # Add buffers to BEFORE and AFTER tiles
        with _timed(tile_timings, "buffer"):

            before_buffered, before_core_bounds, before_core_polygon = build_buffered_tile(
                tile_path=before_file,
                tiles_dir=before_folder,
                prefix=before_prefix,
                tile_size=tile_size,
                buffer_distance=buffer_distance,
                output_path=buffered_dir / f"buffered_{before_file.name}",
                pipeline_path=pipeline_dir / f"buffered_{before_file.stem}.json",
                tile_merge_plan=tile_merge_plan,
                env=env
            )

            after_buffered, after_core_bounds, after_core_polygon = build_buffered_tile(
                tile_path=after_path,
                tiles_dir=after_folder,
                prefix=after_prefix,
                tile_size=tile_size,
                buffer_distance=buffer_distance,
                output_path=buffered_dir / f"buffered_{after_path.name}",
                pipeline_path=pipeline_dir / f"buffered_{after_path.stem}.json",
                tile_merge_plan=tile_merge_plan,
                env=env
            )

        before_dem_tile = dem_output_dir / f"before_dem_{tile_stub}.tif"
        after_dem_tile = dem_output_dir / f"after_dem_{tile_stub}.tif"

        # Build BEFORE and AFTER DEM tiles
        with _timed(tile_timings, "DEM"):

            rasterize_tile_dem(
                buffered_tile_path=before_buffered,
                core_bounds=before_core_bounds,
                resolution=before_dem_resolution,
                output_path=before_dem_tile,
                pipeline_path=pipeline_dir / f"dem_{before_file.stem}.json",
                core_polygon_wkt=before_core_polygon,
                crs=output_crs,
                env=env
            )

            rasterize_tile_dem(
                buffered_tile_path=after_buffered,
                core_bounds=after_core_bounds,
                resolution=after_dem_resolution,
                output_path=after_dem_tile,
                pipeline_path=pipeline_dir / f"dem_{after_path.stem}.json",
                core_polygon_wkt=after_core_polygon,
                crs=output_crs,
                env=env
            )

        before_dem_outputs.append(before_dem_tile)
        after_dem_outputs.append(after_dem_tile)

        # One shared global shift for all three clouds of this tile pair
        tile_shift = (
            -float(before_core_bounds[0]),
            -float(before_core_bounds[2]),
            0.0
        )

        # Subsample and align tile pairs
        before_cloud, after_cloud, core_cloud, icp_matrix = align_tile_pair(
            before_buffered,
            after_buffered,
            after_path,
            min_spacing,
            shift=tile_shift,
            min_rms_decrease=icp_min_rms_decrease,
            sampling_limit=icp_sampling_limit,
            timings=tile_timings
        )

        # Keep ICP transformation matrix for later use in swath_profile.py
        icp_transforms[after_path.stem] = {
            "shift": list(tile_shift),
            "matrix": icp_matrix.tolist()
        }

        # Run M3C2 change detection on BEFORE and AFTER tiles
        with _timed(tile_timings, "M3C2"):

            result_cloud = compute_m3c2_change(
                before_cloud,
                after_cloud,
                core_cloud,
                vertical_param_file,
                surface_param_file,
                m3c2_mode,
                m3c2_filter
            )

        # Save compressed AFTER laz tiles with M3C2 change scalar field.
        cloud_output = (
            output_cloud_dir /
            f"M3C2_{after_path.stem}.laz"
        )

        raster_output = (
            output_raster_dir /
            f"M3C2_{after_path.stem}.tif"
        )

        # Rasterize M3C2 change scalar field tiles
        with _timed(tile_timings, "export"):

            rasterize_and_export(
                result_cloud,
                cloud_output,
                raster_output,
                core_bounds=after_core_bounds,
                grid_step=m3c2_raster_resolution,
                output_crs=output_crs
            )

        raster_outputs.append(raster_output)

        # Clear memory
        cc.deleteEntity(before_cloud)
        cc.deleteEntity(after_cloud)
        cc.deleteEntity(result_cloud)
        before_cloud = None
        after_cloud = None
        core_cloud = None
        result_cloud = None

        before_buffered.unlink(missing_ok=True)
        after_buffered.unlink(missing_ok=True)

        for stage, seconds in tile_timings.items():
            run_timings[stage] += seconds

        print(
            f"Stage times: {_format_stage_times(tile_timings)}"
        )

    if not raster_outputs:

        raise RuntimeError(
            f"None of the {len(before_files)} before-event tile(s) had a "
            f"matching after-event tile, so no change was computed "
            f"(unmatched: {unmatched_tiles}). Both epochs must be retiled "
            f"into the same output folder with the same TILE_SIZE."
        )

    # Save ICP transforms for later use
    save_icp_transforms(output_cloud_dir / "icp_transforms.json", icp_transforms)

    finishing_start = time.perf_counter()

    # Merge individual raster tiles into merged tif files
    merge_rasters(
        raster_outputs,
        merged_raster_path
    )

    for tile_raster in raster_outputs:
        tile_raster.unlink(missing_ok=True)

    # Clip away buffered zone in rasters
    clip_raster_to_polygon(merged_raster_path, crop_polygon, crs=output_crs)

    # BEFORE DEM tile merging and processing operations
    if before_dem_outputs:

        merge_rasters(
            before_dem_outputs,
            merged_before_dem_path
        )

        for tile_dem in before_dem_outputs:
            tile_dem.unlink(missing_ok=True)

        # fill in holes using interpolation and clip again to AOI
        clip_raster_to_polygon(merged_before_dem_path, crop_polygon, crs=output_crs)
        fill_dem_holes(merged_before_dem_path)
        clip_raster_to_polygon(merged_before_dem_path, crop_polygon, crs=output_crs)

        # generate slope and hillshade rasters for visualization
        generate_slope_and_hillshade(
            merged_before_dem_path,
            before_slope_path,
            before_hillshade_path
        )

    # AFTER DEM tile merging and processing operations
    if after_dem_outputs:

        merge_rasters(
            after_dem_outputs,
            merged_after_dem_path
        )

        for tile_dem in after_dem_outputs:
            tile_dem.unlink(missing_ok=True)

        # fill in holes using interpolation and clip again to AOI
        clip_raster_to_polygon(merged_after_dem_path, crop_polygon, crs=output_crs)
        fill_dem_holes(merged_after_dem_path)
        clip_raster_to_polygon(merged_after_dem_path, crop_polygon, crs=output_crs)

        # generate slope and hillshade rasters for visualization
        generate_slope_and_hillshade(
            merged_after_dem_path,
            after_slope_path,
            after_hillshade_path
        )

    # Clean up scratch files
    shutil.rmtree(buffered_dir, ignore_errors=True)
    shutil.rmtree(pipeline_dir, ignore_errors=True)
    shutil.rmtree(dem_output_dir, ignore_errors=True)

    _print_timing_summary(
        run_timings,
        time.perf_counter() - finishing_start,
        len(raster_outputs)
    )
