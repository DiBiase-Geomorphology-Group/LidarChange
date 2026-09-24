#!/usr/bin/env zsh
# One-click launcher for LidarChangeNotebook.ipynb on macOS (Apple Silicon).
# The macOS counterpart of launch_notebook.bat - double-click it in Finder.
#
# Replaces the repeated per-session steps:
#   conda activate lidarchange312 / cd CloudComPy312 /
#   source bin/envCloudComPyMacOS.zsh activate / jupyter notebook
# One-time setup (env creation, ipykernel registration, quarantine removal)
# is NOT redone here - run setup_mac.zsh once first.
#
# zsh, not bash: CloudComPy's own env script uses zsh-only syntax (${0:a})
# and refuses to run unless ZSH_EVAL_CONTEXT says it was sourced from a zsh
# file. Under bash it prints "this script must be sourced" and silently
# sets nothing, and "import cloudComPy" then fails in the notebook.

# Finder runs this from the user's home folder, so every path below is
# derived from the script's own location rather than the working directory.
# :A makes it absolute and resolves symlinks, :h takes the directory.
PROJECT_ROOT="${0:A:h}"
ENV_NAME="lidarchange312"
CLOUDCOMPY_DIR="$PROJECT_ROOT/CloudComPy312"
ENV_SCRIPT="$CLOUDCOMPY_DIR/bin/envCloudComPyMacOS.zsh"

# Keep the Terminal window open on failure so the message can be read -
# a .command window that closes instantly shows the user nothing.
fail() {
    print -u2 ""
    print -u2 "$@"
    print -u2 ""
    print -u2 "Press Return to close this window."
    read -r
    exit 1
}

# ---------------------------------------------------------------------------
# Find the conda installation. Checked in this order:
#   1. CONDA_ROOT, if you've set it yourself (to force a specific install)
#   2. CONDA_EXE, which conda sets in shells where it's initialized
#   3. the usual install folders for Miniforge / Miniconda / Anaconda
#   4. a conda found on PATH
# A folder counts as a conda install only if it has etc/profile.d/conda.sh,
# which is what makes "conda activate" work in a non-interactive script.
# ---------------------------------------------------------------------------
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
If conda is installed somewhere unusual, set CONDA_ROOT to its folder first, e.g.:
    export CONDA_ROOT=\$HOME/tools/miniforge3
and run this file again from that same Terminal window."
fi

print "Using conda at: $CONDA_ROOT"

if [[ ! -f "$ENV_SCRIPT" ]]; then
    fail "CloudComPy was not found at \"$CLOUDCOMPY_DIR\".
Expected its environment script at:
    $ENV_SCRIPT

Download the macOS (Apple arm64) CloudComPy binary, unzip it into this
project folder, and rename the unzipped folder to exactly CloudComPy312.
Then run setup_mac.zsh once. See the macOS section of README.md."
fi

source "$CONDA_ROOT/etc/profile.d/conda.sh"
conda activate "$ENV_NAME"
if [[ $? -ne 0 ]]; then
    fail "Failed to activate conda environment \"$ENV_NAME\" using the conda at $CONDA_ROOT.
Has it been created yet? Run setup_mac.zsh once first."
fi

# Sourced from inside CloudComPy312 as its own documentation specifies. The
# script takes "activate" (unlike the Windows .bat, which takes "skip"); with
# no argument it only prints usage and sets nothing.
cd "$CLOUDCOMPY_DIR" || fail "Could not enter \"$CLOUDCOMPY_DIR\"."
source "./bin/envCloudComPyMacOS.zsh" activate
cd "$PROJECT_ROOT" || fail "Could not return to \"$PROJECT_ROOT\"."

# That script works out its own location with realpath on a path that runs
# through a file name ("<...>/envCloudComPyMacOS.zsh/../.."), which BSD
# realpath can reject - leaving PYTHONPATH without CloudComPy in it and the
# notebook failing much later on "import cloudComPy". Check what it actually
# set, and set the same paths here if it came up empty.
if [[ "$CLOUDCOMPY_ENV_ACTIVATED" != "1" || ":$PYTHONPATH:" != *":$CLOUDCOMPY_DIR:"* ]]; then
    print "CloudComPy's env script did not set PYTHONPATH as expected - setting it directly."
    export PYTHONPATH="$CLOUDCOMPY_DIR:$CLOUDCOMPY_DIR/CloudCompare/CloudCompare.app/Contents/Frameworks:$CLOUDCOMPY_DIR/cloudComPy/doc/PythonAPI_test:$PYTHONPATH"
    export LC_NUMERIC=C
fi

# Jupyter is started from the project root because the notebook takes its
# PROJECT_ROOT from the kernel's working directory.
cd "$PROJECT_ROOT" || fail "Could not enter \"$PROJECT_ROOT\"."
jupyter notebook "LidarChangeNotebook.ipynb"
status=$?

# 130 is Ctrl-C, which is the normal way to stop the notebook server.
if (( status != 0 && status != 130 )); then
    fail "Jupyter exited with an error (exit code $status)."
fi
