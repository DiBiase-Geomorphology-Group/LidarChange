"""Generate buffer around tiled point clouds
"""


from collections import defaultdict
from pathlib import Path

from .pdal_runner import run_pipeline, las_writer_stage
from .tile_grid import parse_tile_origin, cells_union_wkt


def build_buffered_tile(
    tile_path,
    tiles_dir,
    prefix,
    tile_size,
    buffer_distance,
    output_path,
    pipeline_path,
    tile_merge_plan=None,
    env=None
):
    """Merge a retiled tile with the overlapping edge strip of its
    existing neighbor tiles (within buffer_distance of the tile's own
    boundary) into one buffered LAS/LAZ file.

    tile_merge_plan if present is the {(llx, lly): (target_llx, target_lly)}
    mapping returned by merge_partial_tiles, if partial-tile merging was run.
    When tile_path is itself a merged tile covering several grid cells,
    its own extent is the union of those cells rather than a single
    tile_size square, so neighbor lookup and cropping widen accordingly.

    Returns (output_path, core_bounds, core_polygon_wkt).
    core_bounds = (xmin, xmax, ymin, ymax) is unbuffered extent, for
    cropping M3C2/DEM outputs back to the tile for merging.
    core_polygon_wkt is the extent of either the single or all merged
    tiles.
    """

    tiles_dir = Path(tiles_dir)
    tile_path = Path(tile_path)

    own_cell = parse_tile_origin(tile_path, prefix)

    if tile_merge_plan:

        member_cells = [
            cell for cell, target in tile_merge_plan.items()
            if target == own_cell
        ] or [own_cell]

        target_counts = defaultdict(int)

        for target in tile_merge_plan.values():

            target_counts[target] += 1

    else:

        member_cells = [own_cell]
        target_counts = {}

    member_xs = [cell[0] for cell in member_cells]
    member_ys = [cell[1] for cell in member_cells]

    core_bounds = (
        min(member_xs),
        max(member_xs) + tile_size,
        min(member_ys),
        max(member_ys) + tile_size
    )

    core_polygon_wkt = (
        cells_union_wkt(member_cells, tile_size)
        if len(member_cells) > 1 else None
    )

    xmin = core_bounds[0] - buffer_distance
    xmax = core_bounds[1] + buffer_distance
    ymin = core_bounds[2] - buffer_distance
    ymax = core_bounds[3] + buffer_distance

    # Every grid cell touching (edge or corner) any of this tile's member
    # cells, excluding the member cells themselves.
    member_set = set(member_cells)
    neighbor_cells = set()

    for (llx, lly) in member_cells:

        for dx in (-tile_size, 0, tile_size):

            for dy in (-tile_size, 0, tile_size):

                neighbor_cell = (llx + dx, lly + dy)

                if neighbor_cell not in member_set:

                    neighbor_cells.add(neighbor_cell)

    # Resolve each neighbor cell to whichever file currently represents it
    neighbor_paths = set()

    for neighbor_cell in neighbor_cells:

        target = (
            tile_merge_plan.get(neighbor_cell, neighbor_cell)
            if tile_merge_plan else neighbor_cell
        )

        suffix = (
            "_merged"
            if target_counts.get(target, 1) > 1
            else ""
        )

        neighbor_path = (
            tiles_dir /
            f"{prefix}{target[0]}_{target[1]}{suffix}{tile_path.suffix}"
        )

        if neighbor_path.exists():

            neighbor_paths.add(neighbor_path)

    # Crop neighbors based on buffer bounds
    buffer_bounds = f"([{xmin},{xmax}],[{ymin},{ymax}])"

    pipeline = [
        {
            "type": "readers.las",
            "filename": str(tile_path),
            "tag": "tile"
        }
    ]

    merge_inputs = ["tile"]

    for i, neighbor_path in enumerate(sorted(neighbor_paths)):

        pipeline.append(
            {
                "type": "readers.las",
                "filename": str(neighbor_path),
                "tag": f"neighbor_{i}"
            }
        )

        pipeline.append(
            {
                "type": "filters.crop",
                "bounds": buffer_bounds,
                "inputs": [f"neighbor_{i}"],
                "tag": f"neighbor_{i}_strip"
            }
        )

        merge_inputs.append(f"neighbor_{i}_strip")

    pipeline.append(
        {
            "type": "filters.merge",
            "inputs": merge_inputs
        }
    )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pipeline.append(las_writer_stage(output_path))

    # Streamed, so memory stays flat however large the tiles are
    run_pipeline(pipeline, pipeline_path, env=env, stream=True)

    return output_path, core_bounds, core_polygon_wkt
