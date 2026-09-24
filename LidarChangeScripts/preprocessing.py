"""Builds the PDAL pipeline that filters, crops, and reprojects
raw LAS/LAZ files and runs it over one epoch.
"""

import json
import tempfile

from pathlib import Path

from .pdal_runner import run_pdal, print_progress
from .crs_utils import reproject_polygon_wkt


def create_pdal_pipeline(
    pipeline_path,
    output_crs,
    input_crs=None,
    crop_polygon=None,
    classify_ground=True,
    compress_output=True,
    compute_boundary=False
):
    """Generate PDAL pipeline and save as json file
    """

    pipeline = []

    reader = {
        "type": "readers.las"
    }

    if input_crs:

        reader["default_srs"] = (
            input_crs
        )

    pipeline.append(reader)

    # Optional raw-data footprint if creating lidar extent
    # shapefile. Traces the outline of every point in cloud
    # and writes to pipeline metadata.
    if compute_boundary:

        pipeline.append(
            {
                "type": "filters.hexbin"
            }
        )

    if classify_ground:

        pipeline.append(
            {
                "type": "filters.range",
                "limits":
                "Classification[2:2]"
            }
        )

    # Crop point cloud to polygon
    if crop_polygon:

        pipeline_crop_polygon = crop_polygon

        if (
            input_crs
            and output_crs
            and input_crs != output_crs
        ):

            pipeline_crop_polygon = reproject_polygon_wkt(
                crop_polygon,
                output_crs,
                input_crs
            )

        pipeline.append(
            {
                "type":
                "filters.crop",
                "polygon":
                pipeline_crop_polygon
            }
        )

    # Project point cloud if needed
    if (
        input_crs
        and output_crs
        and input_crs != output_crs
    ):

        pipeline.append(
            {
                "type":
                "filters.reprojection",
                "in_srs":
                input_crs,
                "out_srs":
                output_crs
            }
        )

    # Write preprocessed files to scratch folder
    writer = {
        "type": "writers.las",
        "a_srs": output_crs
    }

    if compress_output:

        writer["compression"] = "laszip"

    pipeline.append(writer)

    pipeline_path = Path(pipeline_path)
    pipeline_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        pipeline_path,
        "w"
    ) as f:

        json.dump(
            pipeline,
            f,
            indent=4
        )


def preprocess_files(
    files,
    pipeline_file,
    output_suffix,
    output_dir,
    output_extension=".laz",
    label=None,
    env=None
):
    """Run pipeline_file over each of the given LAS/LAZ files within
    the AOI extent.

    Returns a list of per-file boundary WKTs for writing boundary
    shapefile if option is selected.
    """

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    files = [Path(file) for file in files]

    boundaries = []

    progress_label = f"{label}: " if label else ""

    for index, file in enumerate(files, start=1):

        print_progress(
            f"{progress_label}processing file "
            f"{index} of {len(files)}: {file.name}"
        )

        output = output_dir / (
            file.stem +
            output_suffix +
            output_extension
        )

        with tempfile.TemporaryDirectory() as tmp_dir:

            metadata_path = Path(tmp_dir) / "metadata.json"

            run_pdal(
                [
                    "translate",
                    file,
                    output,
                    f"--json={pipeline_file}",
                    f"--metadata={metadata_path}"
                ],
                env=env
            )

            with open(metadata_path) as f:

                stages = json.load(f).get("stages", {})

        hexbin = stages.get("filters.hexbin")

        if hexbin and hexbin.get("boundary"):

            boundaries.append(hexbin["boundary"])

    print_progress(
        f"{progress_label}processed {len(files)} file(s)",
        done=True
    )

    return boundaries
