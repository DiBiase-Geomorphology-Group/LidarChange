"""Script for writing the input parameter files used by M3C2
"""

import os
from pathlib import Path


def write_m3c2_params(
    outfile,
    normal_scale,
    search_scale,
    search_depth,
    normal_mode,
    use_core_points,
    registration_error,
):
    # Set max CPU thread count
    max_threads = os.cpu_count() or 8

    text = f"""
[General]
M3C2VER=1
NormalScale={normal_scale}
NormalMode={normal_mode}
NormalMinScale=10
NormalStep=10
NormalMaxScale=40
NormalUseCorePoints={"true" if use_core_points else "false"}
NormalPreferedOri=4
SearchScale={search_scale}
SearchDepth={search_depth}
SubsampleRadius=10
SubsampleEnabled=false
RegistrationError={registration_error}
RegistrationErrorEnabled=true
UseSinglePass4Depth=false
PositiveSearchOnly=false
UseMedian=false
UseMinPoints4Stat=false
MinPoints4Stat=5
ProjDestIndex=2
UseOriginalCloud=true
ExportStdDevInfo=false
ExportDensityAtProjScale=false
MaxThreadCount={max_threads}
UsePrecisionMaps=false
PM1Scale=1
PM2Scale=1
"""

    with open(outfile, "w") as f:
        f.write(text.strip())

    return outfile


def create_m3c2_parameter_files(
    output_dir,
    normal_scale,
    projection_scale,
    search_depth,
    registration_error,
):
    output_dir = Path(output_dir)

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    surface_param_file = (
        output_dir /
        "m3c2_surface_params.txt"
    )

    vertical_param_file = (
        output_dir /
        "m3c2_vertical_params.txt"
    )

    write_m3c2_params(
        outfile=surface_param_file,
        normal_scale=normal_scale,
        search_scale=projection_scale,
        search_depth=search_depth,
        normal_mode=0,
        use_core_points=True,
        registration_error=registration_error
    )

    write_m3c2_params(
        outfile=vertical_param_file,
        normal_scale=normal_scale,
        search_scale=projection_scale,
        search_depth=search_depth,
        normal_mode=3,
        use_core_points=False,
        registration_error=registration_error
    )

    return (
        surface_param_file,
        vertical_param_file
    )
