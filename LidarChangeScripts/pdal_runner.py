"""Basic tools for running PDAL:finding the executable,
running a pipeline, reporting progress, and writing outputs.
"""

import json
import shutil
import subprocess
import sys

from pathlib import Path


class PdalError(RuntimeError):
    """Carry PDAL's own error output."""


def _find_pdal():
    """Path to the pdal executable belonging to THIS Python environment.
    Looked up from sys.prefix rather than trusted to PATH
    """

    candidates = [
        Path(sys.prefix) / "Library" / "bin" / "pdal.exe",  # Windows conda
        Path(sys.prefix) / "bin" / "pdal"                   # macOS/Linux conda
    ]

    for candidate in candidates:

        if candidate.exists():

            return str(candidate)

    return shutil.which("pdal") or "pdal"


PDAL_EXE = _find_pdal()


def run_pdal(
    args,
    env=None
):
    """Run `pdal <args...>` and return the CompletedProcess."""

    args = [str(arg) for arg in args]

    result = subprocess.run(
        [PDAL_EXE] + args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env
    )

    stderr = (result.stderr or "").strip()

    if result.returncode != 0:

        output = stderr or (result.stdout or "").strip()
        tail = "\n".join(output.splitlines()[-30:])

        raise PdalError(
            f"PDAL command failed (exit code {result.returncode}):\n"
            f"  pdal {' '.join(args)}\n\n"
            f"PDAL said:\n{tail or '(no output)'}"
        )

    if stderr:

        print(stderr)

    return result


_progress_width = 0


def print_progress(
    message,
    done=False
):
    """Overwrite the current output line with message, so a per-item
    counter updates in place.
    """

    global _progress_width

    _progress_width = max(_progress_width, len(message))

    print(
        f"\r{message:<{_progress_width}}",
        end="\n" if done else "",
        flush=True
    )

    if done:

        _progress_width = 0


def las_writer_stage(
    output_path
):
    """writers.las stage for output_path: LAZ-compressed if it ends in
    .laz, uncompressed LAS otherwise.
    """

    writer = {
        "type": "writers.las",
        "filename": str(output_path)
    }

    if Path(output_path).suffix.lower() == ".laz":

        writer["compression"] = "laszip"

    return writer


def run_pipeline(
    stages,
    pipeline_path,
    env=None,
    stream=False,
    metadata_path=None
):
    """Write a list of pipeline stages to pipeline_path as JSON and run
    `pdal pipeline` on it.

    stream=True adds --stream, so points flow through in small chunks and
    memory stays flat however large the inputs are.

    metadata_path, if given, is where PDAL writes the pipeline's metadata.
    """

    pipeline_path = Path(pipeline_path)
    pipeline_path.parent.mkdir(parents=True, exist_ok=True)

    with open(pipeline_path, "w") as f:

        json.dump(stages, f, indent=4)

    args = [
        "pipeline",
        pipeline_path
    ]

    if stream:

        args.append("--stream")

    if metadata_path:

        args.append(f"--metadata={metadata_path}")

    run_pdal(args, env=env)
