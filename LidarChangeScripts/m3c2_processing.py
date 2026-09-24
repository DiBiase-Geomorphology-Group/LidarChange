"""Run M3C2 change detection on before/after tile pair,
correcting sign convention so negative is erosion
"""

import cloudComPy as cc
import cloudComPy.M3C2


# Allowed values for the notebook's M3C2_MODE parameter -- which direction
# change is measured along. M3C2_FILTER (True/False) then decides whether
# that change is masked by the surface-normal run's significant-change field.
M3C2_MODES = ("Vertical", "Surface Normal")

# Colorbar label for each (M3C2_MODE, M3C2_FILTER) combination
M3C2_CHANGE_LABELS = {
    ("Vertical", True): "Vertical M3C2 change (filtered)",
    ("Vertical", False): "Vertical M3C2 change (unfiltered)",
    ("Surface Normal", True): "Surface-Normal M3C2 change (filtered)",
    ("Surface Normal", False): "Surface-Normal M3C2 change (unfiltered)",
}


def _run_m3c2(clouds, param_file):
    """Run M3C2 change detection using CloudComPy
    Raises a clear error on failure.
    """
    result_cloud = cc.M3C2.computeM3C2(clouds, paramFilename=str(param_file))

    if result_cloud is None:
        raise RuntimeError(
            f"CloudComPy M3C2 failed (returned None) with parameter file "
            f"{param_file}. Common causes: too few points in the tile, or "
            f"normal/search scales too small for the point spacing."
        )

    return result_cloud


def _rename_distance_field(result_cloud, field_name):
    """Rename the "M3C2 distance" scalar field to field_name
    to avoid issues with future M3C2 runs.
    """
    dic = result_cloud.getScalarFieldDic()

    cc.ccPointCloud.renameScalarField(
        result_cloud,
        dic["M3C2 distance"],
        field_name
    )

    return result_cloud


def _finalize_single_field(result_cloud, field_name, filter_significant):
    """Flip the sign of the renamed M3C2 distance scalar field so that
    negative values correspond to erosion.
    """
    dic = result_cloud.getScalarFieldDic()

    field_sf = result_cloud.getScalarField(dic[field_name])

    values = -1 * field_sf.toNpArrayCopy()

    if filter_significant:
        sig_change = result_cloud.getScalarField(dic["significant change"])
        values = values * sig_change.toNpArrayCopy()

    field_sf.fromNpArrayCopy(values)

    for field in ["M3C2 distance", "distance uncertainty", "significant change"]:

        dic = result_cloud.getScalarFieldDic()

        if field in dic:
            cc.ccPointCloud.deleteScalarField(result_cloud, dic[field])

    return result_cloud


def compute_m3c2_vertical_unfiltered(before_cloud, after_cloud, core_cloud, vertical_param_file):
    """Run vertical M3C2 only, with no significant-change masking."""
    result_cloud = _run_m3c2([after_cloud, before_cloud, core_cloud], vertical_param_file)

    print("Vertical M3C2 complete")

    _rename_distance_field(result_cloud, "Vert_M3C2")

    return _finalize_single_field(result_cloud, "Vert_M3C2", filter_significant=False)


def compute_m3c2_surface_unfiltered(before_cloud, after_cloud, core_cloud, surface_param_file):
    """Run surface-normal M3C2 only, with no significant-change masking."""
    result_cloud = _run_m3c2([after_cloud, before_cloud, core_cloud], surface_param_file)

    print("Surface-normal M3C2 complete")

    _rename_distance_field(result_cloud, "SurfNorm_M3C2")

    return _finalize_single_field(result_cloud, "SurfNorm_M3C2", filter_significant=False)


def compute_m3c2_vertical_filtered(before_cloud, after_cloud, core_cloud, vertical_param_file, surface_param_file):
    """Run vertical M3C2 then surface-normal M3C2 and mask the vertical
    change by surface-normal significance (DiBiase and Lamb, 2020).

    See details in supplement to:

    DiBiase, R.A., and Lamb, M.P., 2020. Dry sediment loading of headwater
    channels fuels post-wildfire debris flows in bedrock landscapes,
    Geology 48, p. 189-193, https://doi.org/10.1130/G46847.1

    """
    result_cloud = _run_m3c2([after_cloud, before_cloud, core_cloud], vertical_param_file)

    print("Vertical M3C2 complete")

    # Renamed before the surface-normal run below, whose own outputs
    # (including the "significant change" field that masks this one)
    # are added to the same cloud.
    _rename_distance_field(result_cloud, "Vert_M3C2")

    result_cloud = _run_m3c2([after_cloud, before_cloud, result_cloud], surface_param_file)

    print("Surface-normal M3C2 complete")

    return _finalize_single_field(result_cloud, "Vert_M3C2", filter_significant=True)


def compute_m3c2_surface_filtered(before_cloud, after_cloud, core_cloud, surface_param_file):
    """Run surface-normal M3C2 and mask the change by that same run's
    significant-change field.
    """
    result_cloud = _run_m3c2([after_cloud, before_cloud, core_cloud], surface_param_file)

    print("Surface-normal M3C2 complete")

    _rename_distance_field(result_cloud, "SurfNorm_M3C2")

    return _finalize_single_field(result_cloud, "SurfNorm_M3C2", filter_significant=True)


def compute_m3c2_change(before_cloud, after_cloud, core_cloud, vertical_param_file, surface_param_file, m3c2_mode, m3c2_filter):
    """Main M3C2 wrapper function for BEFORE/AFTER tile pair.
    Buffered clouds are used to ensure valid normal/search
    neighborhoods, but only points within tile bounds (core_cloud)
    are used for M3C2 distance calculation.
    """
    if m3c2_mode not in M3C2_MODES:
        raise ValueError(
            f"Unknown M3C2_MODE {m3c2_mode!r}; expected one of "
            f"{list(M3C2_MODES)}"
        )

    if m3c2_filter not in (True, False):
        raise ValueError(
            f"Unknown M3C2_FILTER {m3c2_filter!r}; expected True or False"
        )

    if m3c2_mode == "Vertical":

        if m3c2_filter:
            return compute_m3c2_vertical_filtered(
                before_cloud, after_cloud, core_cloud, vertical_param_file, surface_param_file
            )

        return compute_m3c2_vertical_unfiltered(
            before_cloud, after_cloud, core_cloud, vertical_param_file
        )

    if m3c2_filter:
        return compute_m3c2_surface_filtered(
            before_cloud, after_cloud, core_cloud, surface_param_file
        )

    return compute_m3c2_surface_unfiltered(
        before_cloud, after_cloud, core_cloud, surface_param_file
    )
