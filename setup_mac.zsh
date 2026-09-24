#!/usr/bin/env zsh
# One-time setup for LidarChangeNotebook.ipynb on macOS (Apple Silicon).
#
# Run it once, from Terminal, in the project folder:
#     zsh setup_mac.zsh
#
# Run it from Terminal rather than by double-clicking: a freshly downloaded
# .command file has no execute permission yet, and this script is what grants
# it to launch_notebook.command. After this, launching is a double-click.
#
# What it does:
#   1. checks the Mac and the shell can run CloudComPy at all
#   2. finds conda
#   3. finds the CloudComPy binary release
#   4. clears macOS quarantine flags from it
#   5. creates the lidarchange312 conda environment
#   6. checks that environment is arm64, not Intel-under-Rosetta
#   7. registers the notebook's Jupyter kernel
#   8. imports GDAL, PDAL and CloudComPy together as a real test
#   9. optionally runs CloudComPy's own test suite
#  10. makes launch_notebook.command double-clickable
#
# Re-running it is safe: an existing environment is reused unless you ask
# for it to be rebuilt.

PROJECT_ROOT="${0:A:h}"
ENV_NAME="lidarchange312"
KERNEL_DISPLAY_NAME="Python (LidarChange 3.12)"
CLOUDCOMPY_DIR="$PROJECT_ROOT/CloudComPy312"
ENV_SCRIPT="$CLOUDCOMPY_DIR/bin/envCloudComPyMacOS.zsh"
YML="$PROJECT_ROOT/LidarChangeScripts/install_parameters.yml"
LAUNCHER="$PROJECT_ROOT/launch_notebook.command"

step() {
    print ""
    print "=============================================================="
    print "$@"
    print "=============================================================="
}

fail() {
    print -u2 ""
    print -u2 "SETUP FAILED"
    print -u2 "$@"
    exit 1
}

# ---------------------------------------------------------------------------
step "1/10  Checking this Mac"
# ---------------------------------------------------------------------------
if [[ "$(uname -s)" != "Darwin" ]]; then
    fail "This script is for macOS. On Windows, use launch_notebook.bat instead."
fi

# CloudComPy's macOS binary is built for Apple silicon only - there is no
# Intel build, and no amount of Rosetta makes one work.
if [[ "$(sysctl -n hw.optional.arm64 2>/dev/null)" != "1" ]]; then
    fail "This is an Intel Mac. CloudComPy's macOS binary is built for Apple
silicon (M1/M2/M3/M4) only, so this workflow cannot run here.
Use a Windows machine, or an Apple silicon Mac."
fi

# A Terminal opened with "Open using Rosetta" ticked reports x86_64, and every
# conda environment created from it is an Intel one - which then can't load
# CloudComPy's arm64 libraries.
if [[ "$(uname -m)" != "arm64" ]]; then
    fail "This Terminal is running under Rosetta (uname reports $(uname -m)).
Quit Terminal, find it in Applications/Utilities, press Cmd-I, untick
\"Open using Rosetta\", and run this script again."
fi

print "Apple silicon, running natively. Good."

# ---------------------------------------------------------------------------
step "2/10  Finding conda"
# ---------------------------------------------------------------------------
# Same search order as launch_notebook.command: CONDA_ROOT, then CONDA_EXE,
# then the usual install folders, then PATH. A folder counts as a conda
# install only if it has etc/profile.d/conda.sh.
if [[ -n "$CONDA_ROOT" && ! -f "$CONDA_ROOT/etc/profile.d/conda.sh" ]]; then
    print "CONDA_ROOT is set to \"$CONDA_ROOT\", but no conda installation was found there - searching elsewhere."
    CONDA_ROOT=""
fi

if [[ -z "$CONDA_ROOT" && -n "$CONDA_EXE" ]]; then
    candidate="${CONDA_EXE:h:h}"
    [[ -f "$candidate/etc/profile.d/conda.sh" ]] && CONDA_ROOT="$candidate"
fi

if [[ -z "$CONDA_ROOT" ]]; then
    for candidate in \
        "$HOME/miniforge3" \
        "$HOME/mambaforge" \
        "$HOME/miniconda3" \
        "$HOME/anaconda3" \
        "$HOME/opt/miniconda3" \
        "$HOME/opt/anaconda3" \
        "/opt/miniforge3" \
        "/opt/miniconda3" \
        "/opt/anaconda3" \
        "/opt/homebrew/Caskroom/miniforge/base" \
        "/usr/local/Caskroom/miniforge/base" \
        "/Applications/miniforge3"
    do
        if [[ -f "$candidate/etc/profile.d/conda.sh" ]]; then
            CONDA_ROOT="$candidate"
            break
        fi
    done
fi

if [[ -z "$CONDA_ROOT" ]]; then
    # Only useful if this resolves to a real path: where conda has been set
    # up as a shell function, "command -v" prints just the name "conda".
    conda_on_path="$(command -v conda 2>/dev/null)"
    if [[ "$conda_on_path" == /* ]]; then
        candidate="${conda_on_path:A:h:h}"
        [[ -f "$candidate/etc/profile.d/conda.sh" ]] && CONDA_ROOT="$candidate"
    fi
fi

if [[ -z "$CONDA_ROOT" ]]; then
    fail "Could not find a conda installation (Miniforge, Miniconda or Anaconda).
Install Miniforge for Apple silicon from https://conda-forge.org/download/
(the macOS arm64 installer), then run this script again.
If conda is installed somewhere unusual, set it first:
    export CONDA_ROOT=\$HOME/tools/miniforge3"
fi

print "Using conda at: $CONDA_ROOT"
source "$CONDA_ROOT/etc/profile.d/conda.sh" || fail "Could not load conda from $CONDA_ROOT."

# ---------------------------------------------------------------------------
step "3/10  Finding the CloudComPy binary release"
# ---------------------------------------------------------------------------
if [[ ! -f "$ENV_SCRIPT" ]]; then
    print -u2 "CloudComPy was not found at \"$CLOUDCOMPY_DIR\"."
    print -u2 "Expected its environment script at:"
    print -u2 "    $ENV_SCRIPT"
    print -u2 ""

    # The download unzips to a dated folder name, so the usual mistake is
    # having the release in the right place under the wrong name - or one
    # level too deep, where the zip made its own folder inside CloudComPy312.
    nested=("$CLOUDCOMPY_DIR"/*/bin/envCloudComPyMacOS.zsh(N))
    found=("$PROJECT_ROOT"/CloudComPy*(N/))

    if (( ${#nested} > 0 )); then
        inner="${nested[1]:h:h}"
        print -u2 "The release is one folder too deep, at:"
        print -u2 "    $inner"
        print -u2 ""
        print -u2 "Move its contents up one level, e.g.:"
        print -u2 "    mv \"$inner\" \"$PROJECT_ROOT/CloudComPy312_tmp\""
        print -u2 "    rmdir \"$CLOUDCOMPY_DIR\" && mv \"$PROJECT_ROOT/CloudComPy312_tmp\" \"$CLOUDCOMPY_DIR\""
    elif [[ -d "$CLOUDCOMPY_DIR" ]]; then
        print -u2 "That folder exists but has no macOS environment script in it."
        print -u2 "The Windows release (which has envCloudComPy.bat instead) will not"
        print -u2 "work here - you need the macOS Apple arm64 build, from"
        print -u2 "    https://www.simulation.openfields.fr/index.php/cloudcompy-downloads"
    elif (( ${#found} > 0 )); then
        print -u2 "This project folder does contain:"
        for d in $found; do
            print -u2 "    ${d:t}"
        done
        print -u2 ""
        print -u2 "Rename the one holding the macOS release to exactly CloudComPy312, e.g.:"
        print -u2 "    mv \"${found[1]}\" \"$CLOUDCOMPY_DIR\""
    else
        print -u2 "Download the macOS (Apple arm64) CloudComPy binary from"
        print -u2 "    https://www.simulation.openfields.fr/index.php/cloudcompy-downloads"
        print -u2 "unzip it into this project folder, and rename the unzipped folder"
        print -u2 "to exactly CloudComPy312."
    fi
    fail "Then run this script again."
fi

print "Found CloudComPy at: $CLOUDCOMPY_DIR"

# ---------------------------------------------------------------------------
step "4/10  Clearing macOS quarantine flags"
# ---------------------------------------------------------------------------
# Everything unzipped from a downloaded archive carries com.apple.quarantine.
# Gatekeeper then refuses to load CloudComPy's unsigned libraries, and
# "import cloudComPy" dies with a "developer cannot be verified" dialog for
# each one. Stripping the flag from the whole tree is the documented fix.
xattr -dr com.apple.quarantine "$CLOUDCOMPY_DIR" 2>/dev/null
print "Cleared quarantine flags on $CLOUDCOMPY_DIR"

# ---------------------------------------------------------------------------
step "5/10  Creating the conda environment \"$ENV_NAME\""
# ---------------------------------------------------------------------------
[[ -f "$YML" ]] || fail "Environment file not found: $YML"

if conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
    print "An environment named \"$ENV_NAME\" already exists."
    if read -q "reply?Rebuild it from scratch? [y/N] "; then
        print ""
        conda env remove -y -n "$ENV_NAME" || fail "Could not remove the existing \"$ENV_NAME\" environment."
        create_env=1
    else
        print ""
        print "Keeping the existing environment."
        create_env=0
    fi
else
    create_env=1
fi

if (( create_env )); then
    print "Creating from $YML - this takes several minutes."
    if ! conda env create -n "$ENV_NAME" -f "$YML"; then
        # install_parameters.yml pins most packages to the versions the
        # workflow was tested with on Windows. The geospatial ones known to
        # differ on osx-arm64 are already left loose there, but conda-forge
        # does not build the rest at the identical version either, so a solve
        # can still fail on a Mac where it succeeds on Windows. Retry with
        # the pins dropped from everything but Python.
        print ""
        print "The pinned environment did not solve on this Mac."
        print "Retrying with the version pins relaxed (Python stays at 3.12)."

        # A create that got as far as downloading leaves a partial prefix
        # behind, which would fail the retry with "prefix already exists".
        conda env remove -y -n "$ENV_NAME" >/dev/null 2>&1

        loose_yml="${TMPDIR:-/tmp}/lidarchange_install_parameters_loose.yml"
        sed -E -e 's/^( *- *python)=3\.12[^ ]*/\1=3.12/' \
               -e '/^ *- *python=/!s/^( *- *[A-Za-z0-9_.+-]+)=[^ ]*/\1/' \
               "$YML" > "$loose_yml" \
            || fail "Could not write the relaxed environment file."
        print "Relaxed environment file: $loose_yml"

        conda env create -n "$ENV_NAME" -f "$loose_yml" \
            || fail "Could not create the \"$ENV_NAME\" environment, pinned or relaxed.
The full conda output above says why."

        print ""
        print "NOTE: the environment was built with relaxed pins, so its package"
        print "versions differ from the tested Windows ones. Each run records what"
        print "it actually used in Parameters_<timestamp>/run_config.json."
    fi
fi

conda activate "$ENV_NAME" || fail "Could not activate the \"$ENV_NAME\" environment."
print "Activated $ENV_NAME"

# ---------------------------------------------------------------------------
step "6/10  Checking the environment is arm64"
# ---------------------------------------------------------------------------
env_arch="$(python -c 'import platform; print(platform.machine())' 2>/dev/null)"
if [[ "$env_arch" != "arm64" ]]; then
    fail "The \"$ENV_NAME\" environment is $env_arch, not arm64, so it cannot load
CloudComPy's Apple silicon libraries. This happens when conda itself was
installed as an Intel build, or when CONDA_SUBDIR was set to osx-64.
Install the macOS arm64 Miniforge from https://conda-forge.org/download/
and run this script again."
fi
print "Environment Python is arm64."

# ---------------------------------------------------------------------------
step "7/10  Registering the Jupyter kernel"
# ---------------------------------------------------------------------------
# The notebook records the kernel name "lidarchange312"; without this,
# opening it gives a "kernel not found" prompt.
python -m ipykernel install --user --name "$ENV_NAME" --display-name "$KERNEL_DISPLAY_NAME" \
    || fail "Could not register the Jupyter kernel."

# ---------------------------------------------------------------------------
step "8/10  Testing GDAL, PDAL and CloudComPy together"
# ---------------------------------------------------------------------------
cd "$CLOUDCOMPY_DIR" || fail "Could not enter $CLOUDCOMPY_DIR."
source "./bin/envCloudComPyMacOS.zsh" activate
cd "$PROJECT_ROOT" || fail "Could not return to $PROJECT_ROOT."

if [[ "$CLOUDCOMPY_ENV_ACTIVATED" != "1" || ":$PYTHONPATH:" != *":$CLOUDCOMPY_DIR:"* ]]; then
    print "CloudComPy's env script did not set PYTHONPATH as expected - setting it directly."
    print "(launch_notebook.command applies the same fallback, so this is not fatal.)"
    export PYTHONPATH="$CLOUDCOMPY_DIR:$CLOUDCOMPY_DIR/CloudCompare/CloudCompare.app/Contents/Frameworks:$CLOUDCOMPY_DIR/cloudComPy/doc/PythonAPI_test:$PYTHONPATH"
    export LC_NUMERIC=C
fi

print "Importing (CloudComPy can take a minute)..."
python - <<'PYTEST'
import sys

# The same order the notebook uses: LidarChangeScripts loads GDAL first,
# then cloudComPy. Importing them the other way round is what breaks GDAL.
import LidarChangeScripts
from osgeo import gdal
import cloudComPy

from LidarChangeScripts.pdal_runner import PDAL_EXE, run_pdal

# Reported, not asserted: a banner this doesn't recognise still means PDAL
# ran, and failing setup over the wording would be misleading.
pdal_line = next(
    (
        line.strip()
        for line in run_pdal(["--version"]).stdout.splitlines()
        if line.strip().startswith("pdal ")
    ),
    "pdal               (ran, version line not recognised)"
)

print("")
print(f"  LidarChangeScripts {LidarChangeScripts.__version__}")
print(f"  python             {sys.version.split()[0]}")
print(f"  gdal               {gdal.__version__}")
print(f"  {pdal_line}")
print(f"  pdal executable    {PDAL_EXE}")
print("  cloudComPy         imported")
PYTEST

if [[ $? -ne 0 ]]; then
    fail "The import test failed - the error above says which package.

  \"cannot be opened because the developer cannot be verified\", or a
  crash inside cloudComPy: quarantine flags are still set somewhere.
  Try again:  xattr -dr com.apple.quarantine \"$CLOUDCOMPY_DIR\"

  \"incompatible architecture\": the environment and CloudComPy disagree
  about arm64 vs Intel - see step 6.

  \"No module named cloudComPy\": CloudComPy's env script did not set
  PYTHONPATH. Check that $ENV_SCRIPT exists and that you ran this with
  zsh, not bash or sh."
fi

# ---------------------------------------------------------------------------
step "9/10  CloudComPy's own test suite (optional)"
# ---------------------------------------------------------------------------
# Laid out differently on macOS than on Windows, so both places are checked.
test_dir=""
for candidate in \
    "$CLOUDCOMPY_DIR/cloudComPy/doc/PythonAPI_test" \
    "$CLOUDCOMPY_DIR/doc/PythonAPI_test"
do
    [[ -f "$candidate/CTestTestfile.cmake" ]] && { test_dir="$candidate"; break; }
done

if [[ -z "$test_dir" ]]; then
    print "CloudComPy's test suite was not found in this release - skipping."
elif ! command -v ctest >/dev/null 2>&1; then
    print "ctest is not on PATH (it comes with the cmake package) - skipping."
else
    print "CloudComPy ships a test suite that confirms its own install."
    print "It takes about five minutes and writes ~2 GB to $HOME/CloudComPy/Data."
    if read -q "reply?Run it now? [y/N] "; then
        print ""
        ( cd "$test_dir" && ctest ) \
            && print "CloudComPy's tests passed." \
            || print "Some CloudComPy tests failed. The notebook may still work - the
suite covers far more of CloudCompare than this workflow uses."
    else
        print ""
        print "Skipped. To run it later:"
        print "    cd \"$test_dir\" && ctest"
    fi
fi

# ---------------------------------------------------------------------------
step "10/10  Making launch_notebook.command double-clickable"
# ---------------------------------------------------------------------------
if [[ -f "$LAUNCHER" ]]; then
    chmod +x "$LAUNCHER" || fail "Could not make $LAUNCHER executable."
    xattr -d com.apple.quarantine "$LAUNCHER" 2>/dev/null
    print "$LAUNCHER is now executable."
else
    print -u2 "WARNING: launch_notebook.command is missing from $PROJECT_ROOT."
    print -u2 "Without it, start the notebook by hand each session - see README.md."
fi

print ""
print "=============================================================="
print "Setup complete."
print ""
print "From now on, double-click launch_notebook.command in Finder to"
print "open the notebook. The first time, macOS may ask whether you're"
print "sure you want to open it - choose Open."
print "=============================================================="
