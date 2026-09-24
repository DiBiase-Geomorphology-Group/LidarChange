"""Boundary shapefile tools for lidar data extent
and AOI shapefile processing
"""

from pathlib import Path

import geopandas as gpd

from shapely import wkt
from shapely.ops import unary_union

from osgeo import ogr, osr


def create_extent_shapefile(
    boundaries,
    output_shp,
    crs,
    name
):
    """Generate a polygon of the point cloud footprint
    and save it as a shapefile.
    """

    boundaries = list(boundaries)

    if not boundaries:

        raise ValueError(
            "No boundaries given -- was the pipeline built with "
            "create_pdal_pipeline(..., compute_boundary=True)?"
        )

    polygons = [
        wkt.loads(boundary)
        for boundary in boundaries
    ]

    merged_boundary = unary_union(
        polygons
    )

    gdf = gpd.GeoDataFrame(
        {"name": [name]},
        geometry=[merged_boundary],
        crs=crs
    )

    output_shp = Path(output_shp)
    output_shp.parent.mkdir(parents=True, exist_ok=True)

    gdf.to_file(output_shp)

    print(
        f"\nSaved:\n{output_shp}"
    )

    return output_shp


def buffer_polygon_wkt(
    polygon_wkt,
    distance
):
    """Expand polygon_wkt outward by distance, e.g. to pad an AOI crop
    polygon by BUFFER_DISTANCE before cropping raw data to retain buffer
    for DEM generation and M3C2 calculations at boundaries.
    """

    return wkt.loads(polygon_wkt).buffer(distance).wkt


def polygon_area_m2(
    polygon_wkt,
    crs
):
    """Calculate the true ground area of polygon_wkt with coordinate
    reference system crs, in units of square meters.
    """

    srs = osr.SpatialReference()
    srs.SetFromUserInput(crs)
    srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

    geom = ogr.CreateGeometryFromWkt(polygon_wkt)
    geom.AssignSpatialReference(srs)

    return geom.GeodesicArea()


def shapefile_to_wkt(
    shapefile
):
    """Read the first feature from a shapefile
    and return its geometry as WKT.
    """

    shp = ogr.Open(
        str(shapefile)
    )

    if shp is None:

        raise RuntimeError(
            f"Unable to open shapefile: "
            f"{shapefile}"
        )

    layer = shp.GetLayer(0)

    feature = layer.GetNextFeature()

    if feature is None:

        raise RuntimeError(
            f"No features found in: "
            f"{shapefile}"
        )

    geom = feature.GetGeometryRef()

    return geom.ExportToWkt()


def shapefile_crs_info(
    shapefile
):
    """Read shapefile spatial reference and return
    crs_wkt, epsg, linear_unit_m.
    """

    shp = ogr.Open(
        str(shapefile)
    )

    if shp is None:

        raise RuntimeError(
            f"Unable to open shapefile: "
            f"{shapefile}"
        )

    layer = shp.GetLayer(0)

    srs = layer.GetSpatialRef()

    if srs is None:

        raise RuntimeError(
            f"No spatial reference found in: "
            f"{shapefile}"
        )

    crs_wkt = srs.ExportToWkt()
    linear_unit_m = srs.GetLinearUnits()

    try:

        srs.AutoIdentifyEPSG()

    except Exception:

        pass

    epsg_code = srs.GetAuthorityCode(None)
    epsg = f"EPSG:{epsg_code}" if epsg_code else None

    return crs_wkt, epsg, linear_unit_m
