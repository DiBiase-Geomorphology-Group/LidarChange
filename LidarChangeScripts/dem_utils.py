"""DEM generation, clipping, and processing tools
"""

import os

from pathlib import Path

from osgeo import gdal

from .pdal_runner import run_pipeline

# Define tif creation options (lossless compression, data type, pyramids, etc.)
FLOAT_RASTER_OPTIONS = ["COMPRESS=DEFLATE", "PREDICTOR=3", "TILED=YES", "BIGTIFF=IF_SAFER"]
BYTE_RASTER_OPTIONS = ["COMPRESS=DEFLATE", "PREDICTOR=2", "TILED=YES", "BIGTIFF=IF_SAFER"]


def rasterize_tile_dem(
    buffered_tile_path,
    core_bounds,
    resolution,
    output_path,
    pipeline_path,
    output_type="idw",
    core_polygon_wkt=None,
    crs=None,
    env=None
):
    """Rasterize a buffered ground-point tile into a bare-earth DEM,
    cropped back to the tile's own (unbuffered) extent via core_bounds =
    (xmin, xmax, ymin, ymax).
    """

    xmin, xmax, ymin, ymax = core_bounds

    # Create and run pdal pipeline
    pipeline = [
        str(buffered_tile_path),
        {
            "type": "writers.gdal",
            "filename": str(output_path),
            "resolution": resolution,
            "output_type": output_type,
            "bounds": f"([{xmin},{xmax}],[{ymin},{ymax}])",
            "gdaldriver": "GTiff",
            "data_type": "float32",
            "nodata": -9999
        }
    ]

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    run_pipeline(pipeline, pipeline_path, env=env)

    # Clip raster to core points (tile) extent
    if core_polygon_wkt:

        clip_raster_to_polygon(output_path, core_polygon_wkt, crs=crs)

    return output_path


def clip_raster_to_polygon(raster_path, polygon_wkt, crs=None, nodata=-9999):
    """Clip a raster to a polygon in place, setting every pixel outside
    it to nodata and shrinking the raster to the polygon's bounding box.
    """
    gdal.UseExceptions()

    raster_path = Path(raster_path)
    temp_path = raster_path.with_name(raster_path.stem + "_clip_tmp.tif")

    gdal.Warp(
        str(temp_path),
        str(raster_path),
        cutlineWKT=polygon_wkt,
        cutlineSRS=crs,
        cropToCutline=True,
        dstNodata=nodata,
        creationOptions=FLOAT_RASTER_OPTIONS
    )

    os.replace(temp_path, raster_path)

    return raster_path


def fill_dem_holes(raster_path, max_search_distance=100, smoothing_iterations=0):
    """Fill interior nodata gaps in a mosaicked DEM in place, by
    inverse-distance interpolation from surrounding valid pixels
    """
    gdal.UseExceptions()

    dataset = gdal.Open(str(raster_path), gdal.GA_Update)
    band = dataset.GetRasterBand(1)

    gdal.FillNodata(
        targetBand=band,
        maskBand=None,
        maxSearchDist=max_search_distance,
        smoothingIterations=smoothing_iterations
    )

    band.FlushCache()
    dataset = None


def generate_slope_and_hillshade(dem_path, slope_output_path, hillshade_output_path):
    """Derive a slope raster (degrees) and a hillshade raster from a DEM."""
    gdal.UseExceptions()

    gdal.DEMProcessing(
        str(slope_output_path),
        str(dem_path),
        "slope",
        slopeFormat="degree",
        creationOptions=FLOAT_RASTER_OPTIONS
    )

    gdal.DEMProcessing(
        str(hillshade_output_path),
        str(dem_path),
        "hillshade",
        creationOptions=BYTE_RASTER_OPTIONS
    )
