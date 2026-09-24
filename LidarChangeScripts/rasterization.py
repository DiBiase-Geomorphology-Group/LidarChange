"""Tools for rasterizing M3C2 point cloud tiles and
merging M3C2 and DEM raster tiles
"""

import tempfile
import warnings
from pathlib import Path

import cloudComPy as cc

from osgeo import gdal

from .dem_utils import FLOAT_RASTER_OPTIONS

warnings.filterwarnings(
    "ignore",
    message=".*Setting nodata to nan.*"
)


def rasterize_and_export(after_cloud, cloud_output_path, raster_output_path, core_bounds, grid_step=1, output_crs=None):
    """Save the M3C2 point cloud, rasterize it with CloudComPy, and export
    the M3C2 change band as a .tif file to raster_output_path.
    """
    gdal.UseExceptions()

    # set paths
    cloud_output_path = Path(cloud_output_path)
    raster_output_path = Path(raster_output_path)

    # save M3C2 point cloud
    cc.SavePointCloud(after_cloud, str(cloud_output_path))

    print(f"Saved point cloud:\n{cloud_output_path.name}")

    # Apply global shift and set bounds so grids align
    shift_x, shift_y, _ = after_cloud.getGlobalShift()
    xmin, xmax, ymin, ymax = core_bounds
    half = grid_step / 2

    cloud_box = after_cloud.getOwnBB()
    zmin = cloud_box.minCorner()[2]
    zmax = cloud_box.maxCorner()[2]

    grid_box = cc.ccBBox(
        (xmin + shift_x + half, ymin + shift_y + half, zmin),
        (xmax + shift_x - half, ymax + shift_y - half, zmax),
        True
    )

    # Rasterize the M3C2 point cloud to a temp folder
    with tempfile.TemporaryDirectory() as tmp_dir:

        cc.RasterizeGeoTiffOnly(
            cloud=after_cloud,
            gridStep=grid_step,
            outputRasterZ=True,
            outputRasterSFs=True,
            pathToImages=tmp_dir,
            gridBBox=grid_box
        )

        raster_files = list(Path(tmp_dir).glob("*.tif"))

        if len(raster_files) != 1:
            raise RuntimeError(
                f"Expected CloudComPy to write one raster for "
                f"{cloud_output_path.name}, found {len(raster_files)}."
            )

        # Band 2 is the M3C2 change scalar field.
        dataset = gdal.Translate(
            destName=str(raster_output_path),
            srcDS=str(raster_files[0]),
            bandList=[2],
            outputSRS=output_crs
        )
        dataset = None

    print(f"Saved raster:\n{raster_output_path.name}")


def merge_rasters(raster_paths, merged_output_path):
    """Mosaic per-tile rasters (M3C2 change or DEM) into a single merged .tif file."""
    gdal.UseExceptions()

    merged_output_path = Path(merged_output_path)
    merged_output_path.parent.mkdir(parents=True, exist_ok=True)

    vrt_path = "/vsimem/m3c2_merge.vrt"

    vrt = gdal.BuildVRT(
        vrt_path,
        [str(p) for p in raster_paths]
    )

    gdal.Translate(
        destName=str(merged_output_path),
        srcDS=vrt,
        creationOptions=FLOAT_RASTER_OPTIONS
    )

    vrt = None
    gdal.Unlink(vrt_path)

    print(f"Saved merged raster:\n{merged_output_path.name}")
