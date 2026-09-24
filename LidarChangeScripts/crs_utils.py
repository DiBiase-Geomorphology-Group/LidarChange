"""Coordinate reference systems: describing them, converting between
them, and asking user which one a run should work in.
"""


from osgeo import ogr, osr

from .path_utils import prompt_epsg_code

osr.UseExceptions()


def _horizontal_srs(
    crs
):
    """Extract horizontal component of coordinate reference system
    """

    srs = osr.SpatialReference()
    srs.SetFromUserInput(crs)

    if srs.IsCompound():

        srs.StripVertical()

    srs.SetAxisMappingStrategy(
        osr.OAMS_TRADITIONAL_GIS_ORDER
    )

    return srs


def crs_linear_unit_m(
    crs
):
    """Linear unit of coordinate reference system in meters
    (1.0 for meter-based crs, 0.3048 for feet, "none" for geographic crs)
    """

    srs = _horizontal_srs(crs)

    if srs.IsGeographic():

        return None

    return srs.GetLinearUnits()


def reproject_polygon_wkt(
    polygon_wkt,
    from_crs,
    to_crs
):
    """Reproject a 2D polygon's vertices from from_crs to to_crs.
    """

    source = _horizontal_srs(from_crs)
    target = _horizontal_srs(to_crs)

    if source.IsSame(target):

        return polygon_wkt

    transform = osr.CoordinateTransformation(
        source,
        target
    )

    geom = ogr.CreateGeometryFromWkt(polygon_wkt)
    geom.Transform(transform)

    return geom.ExportToWkt()


def describe_crs(
    crs
):
    """Human-readable name for an "EPSG:<code>" or compound
    "EPSG:<horizontal>+<vertical>" CRS string, e.g.
    "NAD83(2011) / UTM zone 11N + NAVD88 height". Falls back to the
    EPSG code itself wherever a component can't be looked up.
    """

    codes = crs.split("+")
    codes = [codes[0]] + [f"EPSG:{code}" for code in codes[1:]]

    names = []

    for code in codes:

        srs = osr.SpatialReference()

        try:

            srs.SetFromUserInput(code)
            name = srs.GetName()

        except Exception:

            name = None

        names.append(name or code)

    return " + ".join(names)


def prompt_output_crs(
    default_crs=None
):
    """Prompts user to define output coordinate reference system.
    Default is to use the AFTER dataset CRS. Requires projected
    crs with horizontal unit in meters.
    """

    prompt = (
        f"Output Coordinate Reference System\n"
        f"Must be projected CRS with linear unit in meters.\n"
        f"Press OK to keep the AFTER dataset's CRS, or type another "
        f"EPSG code (e.g. EPSG:6340+5703):"
    )

    initial_value = default_crs or ""

    while True:

        entered = prompt_epsg_code(
            prompt,
            initial_value=initial_value
        )

        initial_value = entered

        try:

            unit = crs_linear_unit_m(entered)

        except Exception as error:

            prompt = (
                f"{entered} isn't a CRS GDAL recognizes ({error}).\n"
                f"Enter an EPSG code for a projected CRS in meters "
                f"(e.g. EPSG:6340+5703):"
            )

            continue

        if unit != 1.0:

            described = describe_crs(entered)

            measured = (
                "a geographic (lat/lon) CRS, which has no linear unit"
                if unit is None
                else f"{unit:g} m per horizontal unit"
            )

            prompt = (
                f"{entered} ({described}) is {measured}.\n"
                f"The output CRS has to be a projected CRS in meters -- "
                f"enter another EPSG code (e.g. EPSG:6340+5703):"
            )

            continue

        return entered
