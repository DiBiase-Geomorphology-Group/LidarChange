""" Merges small partial tiles into larger neighbor
Useful to avoid alignment issues with narrow point clouds
"""


from collections import defaultdict
from pathlib import Path

from .pdal_runner import run_pipeline, print_progress, las_writer_stage
from .las_metadata import get_point_count
from .tile_grid import tile_paths, parse_tile_origin


def plan_partial_tile_merges(
    tiles_dir,
    before_prefix,
    after_prefix,
    tile_size,
    min_size_fraction,
    env=None
):
    """Determine which tiles are "partial" based on their point count
    relative to the largest tile.

    Group each partial tile with its largest edge-adjacent neighbor,
    chaining multiple partial tiles together if necessary.

    Returns {(llx, lly): (target_llx, target_lly)} for every tile grid
    in both epochs. A tile that doesn't need merging is mapped to itself.
    """

    tiles_dir = Path(tiles_dir)

    before_tiles = {
        parse_tile_origin(path, before_prefix): path
        for path in tile_paths(tiles_dir, before_prefix)
    }

    after_tiles = {
        parse_tile_origin(path, after_prefix): path
        for path in tile_paths(tiles_dir, after_prefix)
    }

    cells = sorted(set(before_tiles) & set(after_tiles))

    unmatched = set(before_tiles) ^ set(after_tiles)

    if unmatched:

        print(
            f"WARNING: {len(unmatched)} retiled grid cell(s) exist in "
            f"only one epoch and were left out of partial-tile merge "
            f"planning: {sorted(unmatched)}"
        )

    if not cells:

        return {}

    sizes = {}

    for index, cell in enumerate(cells, start=1):

        print_progress(
            f"Counting points in tile {index} of {len(cells)}"
        )

        sizes[cell] = min(
            get_point_count(before_tiles[cell], env=env),
            get_point_count(after_tiles[cell], env=env)
        )

    print_progress(
        f"Counted points in {len(cells)} tile(s)",
        done=True
    )

    largest = max(sizes.values())
    threshold = min_size_fraction * largest

    parent = {cell: cell for cell in cells}
    group_size = dict(sizes)

    def find(cell):

        while parent[cell] != cell:

            parent[cell] = parent[parent[cell]]
            cell = parent[cell]

        return cell

    def union(cell_a, cell_b):

        root_a, root_b = find(cell_a), find(cell_b)

        if root_a == root_b:

            return

        # Keep whichever group is currently bigger as the surviving root
        if group_size[root_a] < group_size[root_b]:

            root_a, root_b = root_b, root_a

        parent[root_b] = root_a
        group_size[root_a] += group_size[root_b]

    cell_set = set(cells)

    changed = True

    while changed:

        changed = False

        for cell in cells:

            root = find(cell)

            if group_size[root] >= threshold:

                continue

            llx, lly = cell

            neighbor_cells = [
                (llx + tile_size, lly),
                (llx - tile_size, lly),
                (llx, lly + tile_size),
                (llx, lly - tile_size)
            ]

            candidates = [
                neighbor for neighbor in neighbor_cells
                if neighbor in cell_set and find(neighbor) != root
            ]

            if not candidates:

                continue

            best_neighbor = max(
                candidates,
                key=lambda neighbor: group_size[find(neighbor)]
            )

            union(root, best_neighbor)

            changed = True

    groups = defaultdict(list)

    for cell in cells:

        groups[find(cell)].append(cell)

    mapping = {}

    for members in groups.values():

        # Name the merged output after whichever member had the largest
        # individual point count
        target = max(members, key=lambda cell: sizes[cell])

        for cell in members:

            mapping[cell] = target

        if len(members) > 1:

            print(
                f"Merging partial tile(s) "
                f"{sorted(cell for cell in members if cell != target)} "
                f"into {target} "
                f"(group size {group_size[find(target)]:,} pts, "
                f"threshold {threshold:,.0f} pts)"
            )

        elif sizes[target] < threshold:

            print(
                f"WARNING: tile at {target} is partial "
                f"({sizes[target]:,} pts < {threshold:,.0f} pts) but has "
                f"no larger neighbor to merge into -- left unmerged"
            )

    return mapping


def apply_tile_merge_plan(
    tiles_dir,
    prefix,
    mapping,
    pipeline_dir,
    env=None
):
    """Apply a tile merge plan from plan_partial_tile_merges
    to one epoch's tile files. Merged tiles are replaced with
    "{prefix}{target_llx}_{target_lly}_merged.las".
    Cells that don't need merging are left untouched.
    """

    tiles_dir = Path(tiles_dir)
    pipeline_dir = Path(pipeline_dir)

    tiles_by_cell = {
        parse_tile_origin(path, prefix): path
        for path in tile_paths(tiles_dir, prefix)
    }

    groups = defaultdict(list)

    for cell, target in mapping.items():

        groups[target].append(cell)

    merge_groups = [
        (target, members)
        for target, members in groups.items()
        if len(members) > 1
    ]

    for index, (target, members) in enumerate(merge_groups, start=1):

        print_progress(
            f"Merging {prefix}tile group "
            f"{index} of {len(merge_groups)}"
        )

        missing = [cell for cell in members if cell not in tiles_by_cell]

        if missing:

            raise FileNotFoundError(
                f"Partial-tile merge plan expected tiles for these grid "
                f"cells to exist for prefix '{prefix}' in {tiles_dir}: "
                f"{missing}"
            )

        member_paths = [tiles_by_cell[cell] for cell in members]

        merged_path = (
            tiles_dir /
            f"{prefix}{target[0]}_{target[1]}_merged{member_paths[0].suffix}"
        )

        pipeline = [str(path) for path in member_paths]

        pipeline.append({"type": "filters.merge"})

        pipeline.append(las_writer_stage(merged_path))

        pipeline_path = (
            pipeline_dir /
            f"merge_{prefix}{target[0]}_{target[1]}.json"
        )

        run_pipeline(pipeline, pipeline_path, env=env)

        for path in member_paths:

            path.unlink()

    if merge_groups:

        print_progress(
            f"Merged {len(merge_groups)} {prefix}tile group(s)",
            done=True
        )


def merge_partial_tiles(
    tiles_dir,
    before_prefix,
    after_prefix,
    tile_size,
    min_size_fraction,
    pipeline_dir,
    env=None
):
    """Wrapper function for creating partial tile merge plan
    and applying this plan to both the before and after tile
    sets.
    """

    mapping = plan_partial_tile_merges(
        tiles_dir=tiles_dir,
        before_prefix=before_prefix,
        after_prefix=after_prefix,
        tile_size=tile_size,
        min_size_fraction=min_size_fraction,
        env=env
    )

    apply_tile_merge_plan(
        tiles_dir=tiles_dir,
        prefix=before_prefix,
        mapping=mapping,
        pipeline_dir=pipeline_dir,
        env=env
    )

    apply_tile_merge_plan(
        tiles_dir=tiles_dir,
        prefix=after_prefix,
        mapping=mapping,
        pipeline_dir=pipeline_dir,
        env=env
    )

    return mapping
