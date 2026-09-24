"""One-time environment setup for the main notebook.
"""
import os
import sys
from datetime import datetime

# The hidden Tk window created by start_tk_before_qt, kept here so it lives
# as long as the kernel does.
_TK_APP_ROOT = None


def put_conda_dlls_first():
    """Put this env's own DLLs (gdal, proj, etc.) at the FRONT of PATH, ahead
    of any CloudComPy/CloudCompare directories already there.

    Windows-only (DLLs are found via PATH there), and safe to call more
    than once: it does nothing if the directory is already first.
    """
    if sys.platform != "win32":
        return

    conda_lib_bin = os.path.join(sys.prefix, "Library", "bin")
    path_entries = os.environ.get("PATH", "").split(os.pathsep)

    if os.path.normcase(path_entries[0]) == os.path.normcase(conda_lib_bin):
        return

    os.environ["PATH"] = conda_lib_bin + os.pathsep + os.environ.get("PATH", "")


def start_tk_before_qt():
    """Open a hidden Tk window, so that Tk owns the process's application
    object before CloudComPy's Qt libraries are imported.

    macOS-only, and safe to call more than once.
    """
    global _TK_APP_ROOT

    if sys.platform != "darwin" or _TK_APP_ROOT is not None:
        return

    import tkinter as tk

    _TK_APP_ROOT = tk.Tk()
    _TK_APP_ROOT.withdraw()


def prepare_environment():
    """Fix up PATH for GDAL (see put_conda_dlls_first), claim the macOS
    application object for Tk (see start_tk_before_qt), and return a
    PDAL-safe environment snapshot.

    Call this before importing cloudComPy: both fixes only work while
    CloudComPy's libraries are not loaded yet.
    """
    put_conda_dlls_first()
    start_tk_before_qt()

    return os.environ.copy()


def _is_inside(path, folder):
    """Whether path is folder itself, or anything underneath it."""
    path = os.path.normcase(os.path.abspath(path))
    folder = os.path.normcase(os.path.abspath(folder))

    return path == folder or path.startswith(folder + os.sep)


def warn_if_cloud_synced(project_root):
    """Print a warning if project_root is inside a cloud-synced folder --
    OneDrive on Windows, iCloud Drive on macOS.
    """
    onedrive_roots = [
        os.environ.get(name)
        for name in ("OneDrive", "OneDriveCommercial", "OneDriveConsumer")
    ]

    for onedrive_root in filter(None, onedrive_roots):
        if _is_inside(project_root, onedrive_root):
            print(
                f"WARNING: this project folder is inside OneDrive "
                f"({os.path.abspath(onedrive_root)}).\n"
                f"OneDrive will try to sync every large intermediate file, and "
                f"its file locks can make the run fail. Move the project to a "
                f"folder that isn't synced (e.g. C:\\LidarProjects) for "
                f"reliable runs."
            )
            return

    if sys.platform == "darwin":
        resolved = os.path.realpath(project_root)

        if _is_inside(resolved, os.path.expanduser("~/Library/Mobile Documents")):
            print(
                f"WARNING: this project folder is inside iCloud Drive "
                f"(it really lives at {resolved}).\n"
                f"iCloud will try to sync every large intermediate file, and it "
                f"can evict files to the cloud part-way through a run. Move the "
                f"project to a folder that isn't synced (e.g. ~/LidarProjects) "
                f"for reliable runs."
            )
            return


def define_preprocess_dir(project_root):
    """The project-level folder holding preprocessed point clouds, created
    if it doesn't exist yet. This folder is not timestamped and the preprocessed
    point clouds can be used multiple times for runs with different parameters
    for efficiency.
    """
    warn_if_cloud_synced(project_root)

    preprocess_dir = project_root / "Preprocessed"
    preprocess_dir.mkdir(parents=True, exist_ok=True)

    return preprocess_dir


def define_project_directories(project_root, run_timestamp=None):
    """Derive the project's input/output directories from PROJECT_ROOT,
    creating the scratch directory if it doesn't exist yet.

    The Outputs and Parameters folders are suffixed with run_timestamp
    (default: the current time, as YYYYMMDD_HHMMSS) so each notebook run
    gets its own folders instead of overwriting the previous run.

    Returns (cloudcompy_dir, outputs_dir, tiles_dir, rasters_dir, m3c2_dir,
    visualization_dir, parameters_dir, scratch_dir).
    """
    if run_timestamp is None:
        run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    cloudcompy_dir = project_root / "CloudComPy312"

    outputs_dir = project_root / f"Outputs_{run_timestamp}"
    tiles_dir = outputs_dir / "Tiled point clouds"
    rasters_dir = outputs_dir / "Rasters"
    m3c2_dir = outputs_dir / "M3C2"
    visualization_dir = outputs_dir / "Visualization"
    parameters_dir = project_root / f"Parameters_{run_timestamp}"

    # Scratch folder for this run's own intermediate files (tiles, DEM tiles,
    # raster tiles). It lives under Outputs so it survives kernel restarts,
    # and is deleted at the end of the M3C2 processing cell once a run
    # finishes end-to-end.
    scratch_dir = outputs_dir / "scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)

    return (
        cloudcompy_dir,
        outputs_dir,
        tiles_dir,
        rasters_dir,
        m3c2_dir,
        visualization_dir,
        parameters_dir,
        scratch_dir
    )
