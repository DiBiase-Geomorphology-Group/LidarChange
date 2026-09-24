"""Write a JSON record of the input data and parameters for each run.
"""
import json
import os
import platform
import re
import sys
from datetime import datetime
from pathlib import Path

# Only these value types are recorded as parameters
_SIMPLE_TYPES = (str, int, float, bool, type(None), Path)


def _to_json(value):
    """Value in a JSON-friendly form (paths as strings, tuples as lists)."""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [_to_json(item) for item in value]
    return value


def collect_parameters(namespace):
    """Collect every ALL-CAPS name in the notebook's global variables
    (i.e., notebook parameters, input paths, output folders)

    Does not include swath profile parameters.
    """
    parameters = {}

    for name, value in sorted(namespace.items()):

        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", name) or name.startswith("PROFILE_"):
            continue

        items = value if isinstance(value, (list, tuple)) else [value]

        if all(isinstance(item, _SIMPLE_TYPES) for item in items):
            parameters[name] = _to_json(value)

    return parameters


def _cloudcompy_release(cloudcompy_dir):
    """Return the CloudComPy release date from its release notes.
    """
    cloudcompy_dir = Path(cloudcompy_dir)

    # Could be in a few different places depending on OS
    candidates = [
        cloudcompy_dir / "doc" / "ReleaseNotes.md",
        cloudcompy_dir / "cloudComPy" / "doc" / "ReleaseNotes.md",
    ]

    for notes in candidates:

        try:
            text = notes.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        match = re.search(r"^##\s+(.+?)\s+CloudComPy release", text, re.MULTILINE)

        if match:
            return match.group(1)

    return None


def collect_versions(cloudcompy_dir=None, env=None):
    """Return the versions of this notebook workflow and its main dependencies"""
    from osgeo import gdal, osr
    import numpy

    from . import __version__
    from .pdal_runner import run_pdal

    # extract version from `pdal --version` banner output
    try:
        output = run_pdal(["--version"], env=env).stdout
        pdal_version = next(
            line.split("(")[0].strip()
            for line in output.splitlines()
            if line.strip().startswith("pdal ")
        )
    except Exception as error:
        pdal_version = f"unknown ({error})"

    # PROJ's version and the grids it reads decide how the vertical datum
    # transforms come out, so record both
    proj_version = ".".join(
        str(part) for part in (
            osr.GetPROJVersionMajor(),
            osr.GetPROJVersionMinor(),
            osr.GetPROJVersionMicro()
        )
    )

    versions = {
        "LidarChangeScripts": __version__,
        "python": sys.version.split()[0],
        "gdal": gdal.__version__,
        "proj": proj_version,
        "proj_network": os.environ.get("PROJ_NETWORK", "unset"),
        "pdal": pdal_version,
        "numpy": numpy.__version__,
        "platform": platform.platform(),
    }

    if cloudcompy_dir is not None:
        versions["cloudcompy_release"] = _cloudcompy_release(cloudcompy_dir)

    return versions


def write_run_record(record_path, namespace, extra=None, cloudcompy_dir=None, env=None):
    """Write the run record as JSON file.

    namespace is the notebook's globals()
    extra holds other parameters like detected CRSs
    """
    record = {
        "created": datetime.now().isoformat(timespec="seconds"),
        "versions": collect_versions(cloudcompy_dir=cloudcompy_dir, env=env),
        "parameters": collect_parameters(namespace),
        "details": {key: _to_json(value) for key, value in (extra or {}).items()},
    }

    record_path = Path(record_path)
    record_path.parent.mkdir(parents=True, exist_ok=True)

    with open(record_path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)

    print(f"Saved run record: {record_path}")

    return record_path


def warn_if_parameters_changed(record_path, namespace):
    """Print a warning listing any parameter whose current value differs
    from the one saved in the run record.
    """
    record_path = Path(record_path)

    if not record_path.exists():
        print(f"WARNING: no run record found at {record_path}")
        return []

    with open(record_path, encoding="utf-8") as f:
        recorded = json.load(f)["parameters"]

    current = collect_parameters(namespace)

    changed = sorted(
        name for name in set(recorded) | set(current)
        if recorded.get(name) != current.get(name)
    )

    if changed:
        print(
            f"WARNING: these parameters changed since this run started (see "
            f"{record_path.name}): {', '.join(changed)}.\n"
            f"The run record, and any earlier steps of this run, used the old "
            f"values. For consistent results, re-run from the 'Start a new "
            f"run' cell."
        )

    return changed
