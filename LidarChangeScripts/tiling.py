"""Tile preprocessed clouds for one epoch into a regular grid
and save the resulting tiles in the Outputs folder.
"""

from collections import defaultdict
from pathlib import Path

from .pdal_runner import run_pdal, run_pipeline, print_progress, las_writer_stage
from .las_metadata import read_las_header
from .tile_grid import tile_paths


def retile_clouds(
    input_dir,
    output_dir,
    input_pattern,
    output_prefix,
    tile_size=2000,
    origin_x=0,
    origin_y=0,
    output_extension=".las",
    env=None
):
    """Process every file matching input_pattern in input_dir into
    tile_size x tile_size tiles on a grid anchored at (origin_x, origin_y),
    written to output_dir as "{output_prefix}{llx}_{lly}{output_extension}".
    """

    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    temp_prefix = f"_tiling_{output_prefix}"

    if not list(input_dir.glob(input_pattern)):

        raise FileNotFoundError(
            f"No files matching '{input_pattern}' in {input_dir}. Run the "
            f"PDAL preprocessing cell first."
        )

    existing_tiles = tile_paths(output_dir, output_prefix)

    if existing_tiles:

        raise FileExistsError(
            f"{len(existing_tiles)} '{output_prefix}' tile(s) already exist "
            f"in {output_dir} (e.g. {existing_tiles[0].name})"
        )

    # Flag presence of fragments from an earlier run
    for stale_fragment in output_dir.glob(f"{temp_prefix}*"):

        stale_fragment.unlink()

    run_pdal(
        [
            "tile",
            input_dir / input_pattern,
            output_dir / f"{temp_prefix}#{output_extension}",
            f"--origin_x={origin_x}",
            f"--origin_y={origin_y}",
            f"--length={tile_size}"
        ],
        env=env
    )

    tiled_files = list(
        output_dir.glob(
            f"{temp_prefix}*{output_extension}"
        )
    )

    if not tiled_files:

        raise RuntimeError(
            f"pdal tile produced no tiles from {input_dir / input_pattern} "
            f"-- the preprocessed files are probably empty (no ground "
            f"points inside the AOI)."
        )

    # Group fragments by their target cell first, so a cell with only one
    # fragment is just renamed, and a cell with several is merged into
    # one file.
    fragments_by_cell = defaultdict(list)

    for index, tiled_file in enumerate(tiled_files, start=1):

        print_progress(
            f"Grouping {output_prefix}fragment "
            f"{index} of {len(tiled_files)}"
        )

        bounds = read_las_header(tiled_file, env=env)

        # Round down to the tile's grid corner
        # so filenames are multiples of tile_size.
        llx = origin_x + tile_size * (
            (bounds["minx"] - origin_x)
            // tile_size
        )

        lly = origin_y + tile_size * (
            (bounds["miny"] - origin_y)
            // tile_size
        )

        cell = (int(round(llx)), int(round(lly)))

        fragments_by_cell[cell].append(tiled_file)

    for index, ((llx, lly), fragments) in enumerate(
        fragments_by_cell.items(),
        start=1
    ):

        print_progress(
            f"Writing {output_prefix}tile "
            f"{index} of {len(fragments_by_cell)}"
        )

        renamed_file = output_dir / (
            f"{output_prefix}"
            f"{llx}_"
            f"{lly}{output_extension}"
        )

        if len(fragments) == 1:

            fragments[0].rename(renamed_file)

            continue

        merge_pipeline = [
            str(fragment) for fragment in fragments
        ]

        merge_pipeline.append(
            {"type": "filters.merge"}
        )

        merge_pipeline.append(
            las_writer_stage(renamed_file)
        )

        merge_pipeline_path = (
            output_dir /
            f"_merge_{temp_prefix}_{llx}_{lly}.json"
        )

        run_pipeline(merge_pipeline, merge_pipeline_path, env=env)

        merge_pipeline_path.unlink()

        for fragment in fragments:

            fragment.unlink()

    print_progress(
        f"Wrote {len(fragments_by_cell)} {output_prefix}tile(s)",
        done=True
    )


def archive_tiles(
    tiles_dir,
    archive_dir,
    prefixes,
    env=None
):
    """Write a LAZ-compressed copy of every tile from tiles_dir into
    archive_dir, as "<tile name>.laz".
    """

    archive_dir = Path(archive_dir)
    archive_dir.mkdir(parents=True, exist_ok=True)

    archived = []

    tiles = [
        tile
        for prefix in prefixes
        for tile in tile_paths(tiles_dir, prefix)
    ]

    for index, tile in enumerate(tiles, start=1):

        print_progress(
            f"Compressing tile {index} of {len(tiles)}"
        )

        archive_path = archive_dir / f"{tile.stem}.laz"

        run_pdal(
            [
                "translate",
                tile,
                archive_path,
                "--writers.las.compression=laszip"
            ],
            env=env
        )

        archived.append(archive_path)

    print_progress(
        f"Saved {len(archived)} compressed tile(s) to {archive_dir}",
        done=True
    )

    return archived
