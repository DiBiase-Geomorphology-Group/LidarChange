"""A project-level cache of preprocessed (ground-filtered, clipped,
reprojected) point clouds, shared by every run.

Preprocessing depends only on the input datasets, the AOI, and the output
CRS. A fingerprint of these inputs is stored beside the cache and checked
on every run. If anything changes, the cached clouds are deleted before
being rebuilt.
"""
import hashlib
import json
import shutil
from pathlib import Path

# The fingerprint of the inputs the cached clouds were built from.
FINGERPRINT_NAME = "preprocess_config.json"

# One subfolder of preprocessed clouds per epoch.
EPOCH_SUBDIRS = ("before", "after")

# What preprocess_files(output_suffix="_processed") leaves in them, and
# what the retiling cell later reads back.
PROCESSED_PATTERN = "*_processed.las"

# Artifacts written next to the clouds and copied into each run's own
# folders by copy_preprocess_artifacts.
PIPELINE_PATTERN = "*_pipeline.json"
EXTENT_PATTERN = "*_raw_lidar_extent.*"


def _files_digest(files):
    """A digest of a file list's names, sizes, and modification times --
    enough to notice a dataset being swapped, added to, or re-exported,
    without storing every filename in the fingerprint.
    """
    parts = []

    for file in sorted(Path(file) for file in files):

        stat = file.stat()
        parts.append(f"{file.name}|{stat.st_size}|{stat.st_mtime_ns}")

    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def _text_digest(text):
    """A digest of a long string (e.g. the AOI polygon's WKT), so the
    fingerprint file stays readable.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def preprocess_fingerprint(
    before_dir,
    after_dir,
    before_files,
    after_files,
    before_crs,
    after_crs,
    output_crs,
    aoi_path,
    crop_polygon_padded,
    aoi_buffer,
    make_extent_shapefiles
):
    """Everything the preprocessed clouds depend on, as a JSON-friendly
    dict.
    """
    return {
        "before_dir": str(before_dir),
        "after_dir": str(after_dir),
        "before_file_count": len(before_files),
        "after_file_count": len(after_files),
        "before_files_digest": _files_digest(before_files),
        "after_files_digest": _files_digest(after_files),
        "before_crs": before_crs,
        "after_crs": after_crs,
        "output_crs": output_crs,
        "aoi_path": str(aoi_path),
        "aoi_polygon_digest": _text_digest(crop_polygon_padded),
        "aoi_buffer_m": aoi_buffer,
        "make_extent_shapefiles": bool(make_extent_shapefiles)
    }


# Fingerprint keys whose values are digests, and so mean nothing to read
# back -- reported by what they stand for instead.
_DIGEST_REASONS = {
    "before_files_digest": "the BEFORE files changed on disk",
    "after_files_digest": "the AFTER files changed on disk",
    "aoi_polygon_digest": "the AOI polygon changed"
}


def _describe_change(key, saved, current):
    """One readable line explaining why a fingerprint key no longer
    matches, for the notebook to print.
    """
    if key in _DIGEST_REASONS:
        return _DIGEST_REASONS[key]

    return f"{key}: {saved.get(key)!r} -> {current.get(key)!r}"


def cache_status(preprocess_dir, fingerprint, force=False):
    """Determine whether the cached preprocessing can be reused for this run.

    Returns (reusable, reasons); reasons holds readable lines explaining
    why not, and is empty when the cache is good.
    """
    preprocess_dir = Path(preprocess_dir)

    if force:
        return False, ["FORCE_PREPROCESS is True"]

    saved_path = preprocess_dir / FINGERPRINT_NAME

    if not saved_path.exists():
        return False, ["no cached preprocessing found"]

    try:
        saved = json.loads(saved_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False, [f"could not read {FINGERPRINT_NAME}"]

    changed = sorted(
        key
        for key in set(saved) | set(fingerprint)
        if saved.get(key) != fingerprint.get(key)
    )

    if changed:
        return False, [
            _describe_change(key, saved, fingerprint)
            for key in changed
        ]

    # A fingerprint is only written after a successful run, but the clouds
    # themselves can still have been deleted by hand since.
    missing = [
        name
        for name in EPOCH_SUBDIRS
        if not any((preprocess_dir / name).glob(PROCESSED_PATTERN))
    ]

    if missing:
        return False, [
            f"cached {name} clouds are missing"
            for name in missing
        ]

    return True, []


def cached_file_counts(preprocess_dir):
    """Count number of preprocessed clouds the cache holds for each epoch."""
    preprocess_dir = Path(preprocess_dir)

    return {
        name: len(list((preprocess_dir / name).glob(PROCESSED_PATTERN)))
        for name in EPOCH_SUBDIRS
    }


def clear_preprocess_cache(preprocess_dir):
    """Empty the cache before rebuilding it.

    The fingerprint is removed first, so preprocessing interrupted partway
    through can't leave behind a fingerprint claiming a half-written cache
    is complete.
    """
    preprocess_dir = Path(preprocess_dir)

    (preprocess_dir / FINGERPRINT_NAME).unlink(missing_ok=True)

    for name in EPOCH_SUBDIRS:
        shutil.rmtree(preprocess_dir / name, ignore_errors=True)

    for pattern in (PIPELINE_PATTERN, EXTENT_PATTERN):
        for stale in preprocess_dir.glob(pattern):
            stale.unlink()


def write_preprocess_fingerprint(preprocess_dir, fingerprint):
    """Record the fingerprint, once preprocessing has finished."""
    path = Path(preprocess_dir) / FINGERPRINT_NAME

    with open(path, "w", encoding="utf-8") as f:
        json.dump(fingerprint, f, indent=2)

    return path


def copy_preprocess_artifacts(preprocess_dir, parameters_dir, tiles_dir):
    """Copy the cache's PDAL pipeline files and raw-extent shapefiles into
    this run's own folders, so each Outputs_<timestamp> stays a complete
    record of how its results were made even though the preprocessing
    behind them is shared.

    Returns the list of files copied.
    """
    preprocess_dir = Path(preprocess_dir)
    copied = []

    pipelines = sorted(preprocess_dir.glob(PIPELINE_PATTERN))

    if pipelines:

        parameters_dir = Path(parameters_dir)
        parameters_dir.mkdir(parents=True, exist_ok=True)

        for pipeline in pipelines:
            copied.append(shutil.copy2(pipeline, parameters_dir / pipeline.name))

    # Only present when the run that built the cache had
    # MAKE_EXTENT_SHAPEFILES set.
    extents = sorted(preprocess_dir.glob(EXTENT_PATTERN))

    if extents:

        tiles_dir = Path(tiles_dir)
        tiles_dir.mkdir(parents=True, exist_ok=True)

        for extent in extents:
            copied.append(shutil.copy2(extent, tiles_dir / extent.name))

    return [Path(path) for path in copied]
