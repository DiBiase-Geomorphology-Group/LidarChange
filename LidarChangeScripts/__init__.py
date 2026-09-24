"""Helper package for LidarChangeNotebook.ipynb.

On Windows GDAL and CloudComPy ship different builds of the same DLLs,
and whichever loads first is kept for the rest of the Python session:
if cloudComPy's load first, "from osgeo import gdal" fails with
"DLL load failed while importing _gdal". Loading GDAL here, first, means
the package's own modules can be imported in any order.
"""
import sys

from .environment_setup import put_conda_dlls_first

# Version of this workflow (the notebook + this package)
__version__ = "0.1.0-beta"

if (
    ("cloudComPy" in sys.modules or "_cloudComPy" in sys.modules)
    and "osgeo.gdal" not in sys.modules
):
    raise ImportError(
        "CloudComPy was imported before LidarChangeScripts, so GDAL can no "
        "longer load (CloudComPy's own GDAL/PROJ DLLs are already in use). "
        "Restart the kernel and import from LidarChangeScripts before "
        "'import cloudComPy'."
    )

put_conda_dlls_first()

try:
    from osgeo import gdal  # noqa: F401 -- imported for its DLL load order
except ImportError as error:
    if sys.platform == "win32":
        advice = (
            "If the message mentions a DLL, another program's GDAL/PROJ DLLs "
            "are probably shadowing this environment's: start Jupyter with "
            "launch_notebook.bat, or from a fresh shell with only "
            "'conda activate lidarchange312' plus envCloudComPy.bat, and "
            "restart the kernel."
        )
    else:
        advice = (
            "Start Jupyter with launch_notebook.command rather than by hand, "
            "and restart the kernel. If it still fails, the lidarchange312 "
            "environment is incomplete -- re-run setup_mac.zsh."
        )

    raise ImportError(f"GDAL failed to import ({error}). {advice}") from error
