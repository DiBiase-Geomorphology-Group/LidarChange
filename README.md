# LidarChange

Jupyter notebook and Python scripts for processing and visualizing point-cloud-based lidar change detection. Includes tools for reprojection, tiling, ICP alignment, M3C2 change detection, raster visualization, and point profile creation.

Built for mountain landscapes where change is small and localized relative
to the relief and area of interest. Be sure to inspect output to check
appropriateness of ICP alignment.

Brandon T. Fong and Roman A. DiBiase  
Department of Geosciences, Pennsylvania State University  
contact: brandonfong@psu.edu

> **Beta** (`0.1.0-beta`). Runs on Windows 10/11, and on macOS on Apple
> silicon. The macOS side is less exercised than the Windows side.
> Please report any issues!

## What it does

The notebook runs as ten numbered cells, in order:

1. **Prepare environment** — load libraries in the order that keeps GDAL and
   CloudComPy from colliding
2. **Input data** — pick the before/after folders and the AOI shapefile
3. **Diagnostics** — report each dataset's coordinate reference system (CRS),
   ground-point density and survey dates before committing to a run
4. **Preprocess** — ground-classify, clip to the AOI and reproject both epochs
5. **Parameters** — set tiling, M3C2, and visualization parameters
6. **Initialize run** — create a timestamped output folder
7. **Retile** — tile both epochs into a shared grid
8. **Change detection** — subsample, ICP-align, and run M3C2 on each tile pair
9. **Visualization** — show before/after topography and M3C2 change maps
10. **Swath profiles** — interactive point-cloud cross-section generator

M3C2 runs in either `Vertical` or `Surface Normal` mode, filtered or
unfiltered by the significant-change threshold.

### Outputs

Each run writes two timestamped folders at the project root.

`Outputs_<timestamp>/` holds the data:

- `Tiled point clouds/` — projected, tiled, ground-classified clouds for both
  epochs, and the aligned after-epoch clouds carrying the M3C2 distance
  scalar field
- `Rasters/` — DEM, slope and hillshade for both epochs
- `M3C2/` — the gridded change raster and aligned AFTER clouds with M3C2 scalar field
- `Visualization/` — figures from cells 9 and 10

`Parameters_<timestamp>/` holds the M3C2 parameter files and `run_config.json`,
 which holds parameters, detected CRSs, and package versions used for the run.

Cell 4's preprocessed clouds are cached separately in `Preprocessed/` at the
project root. They are shared by every run and rebuilt only when the input
folders, the AOI or the output CRS change. Re-running with different
tiling or M3C2 parameters skips this step. Delete the folder any time
to reclaim disk space.

## Getting started

Both Windows and macOS need the same four things:

1. a conda installation (e.g., Miniforge, Miniconda)
2. the `lidarchange312` conda environment, built from
   [`LidarChangeScripts/install_parameters.yml`](LidarChangeScripts/install_parameters.yml),
3. a Jupyter kernel registered under the name `lidarchange312` — the name the
   notebook records, and
4. a [CloudComPy](https://www.simulation.openfields.fr/index.php/cloudcompy-downloads)
   binary release for your platform, unpacked into the project folder as
   `CloudComPy312/`.

After initial setup (see below), each session is a double-click on the launcher
for your platform. The launcher does only the per-session work (activating
the environment, loading CloudComPy's own environment, and starting Jupyter
from the project folder).

Download the **Python 3.12** CloudComPy release. Earlier releases were built
against Python 3.10 or 3.11 and won't import in this environment.

### Windows

1. Install [Miniforge](https://conda-forge.org/download/).

2. Open a Miniforge Prompt in the project folder and create the environment:

   ```bash
   conda env create -n lidarchange312 -f LidarChangeScripts/install_parameters.yml
   ```

3. Register the notebook's kernel:

   ```bash
   conda activate lidarchange312
   python -m ipykernel install --user --name lidarchange312 --display-name "Python (LidarChange 3.12)"
   ```

4. Download the Windows CloudComPy binary and unpack it into the project
   folder so that `CloudComPy312\envCloudComPy.bat` exists.

5. Double-click **`launch_notebook.bat`**.

### macOS (Apple silicon)

Check first that this is an Apple silicon Mac — the Apple menu → About This
Mac should say Apple M1/M2/M3/M4, not Intel. CloudComPy's macOS binary is
arm64-only and there is no Intel equivalent.

1. Install [Miniforge](https://conda-forge.org/download/), taking the **macOS
   arm64 (Apple silicon)** installer. An Intel build of conda, even under
   Rosetta, produces an environment that can't load CloudComPy.

2. Download the macOS CloudComPy binary (`CloudComPy_Conda312_MacOS-<date>.zip`),
   unzip it into the project folder, and rename the unzipped folder to exactly
   `CloudComPy312`, so that `CloudComPy312/bin/envCloudComPyMacOS.zsh` exists.

3. Open Terminal in the project folder and run the setup script:

   ```bash
   zsh setup_mac.zsh
   ```

   It finds conda, clears the macOS quarantine flags from CloudComPy, creates
   the environment, registers the kernel, imports GDAL, PDAL and CloudComPy
   together as a test, and enables the launcher.

4. Double-click **`launch_notebook.command`**. The first time, macOS will ask
   whether you're sure you want to open it — choose Open.

The one-off difference from Windows is Gatekeeper: everything unzipped from a
downloaded archive is quarantined, and macOS will refuse to load CloudComPy's
unsigned libraries until that flag is cleared. `setup_mac.zsh` does it, but by
hand it is:

```bash
xattr -dr com.apple.quarantine CloudComPy312
```

### Preparing your data

A small example dataset for testing can be [downloaded here](https://tinyurl.com/4pzvh273) (152 MB)

For your own data:
- One folder of `.las`/`.laz` files per epoch, under a project folder such as
  `Inputs/Tutorial`.
- An AOI polygon as a shapefile. [geojson.io](https://geojson.io/) is a quick
  way to draw one.
- Areas over ~100 km² are worth splitting into several AOIs, to keep the
  merged rasters a manageable size. A ~10 km² AOI takes roughly 10–20 minutes
  on a laptop.
- Know your vertical CRS, or at least whether its units are meters or feet.

Default parameters suit typical airborne lidar in mountainous terrain
(~1–10 ground points/m²).

Note: Keep the project folder out of any syncing cloud folder.

## Repository layout

`LidarChangeNotebook.ipynb` is the workflow. Its launchers and setup script sit
beside it:

| File | |
|---|---|
| `launch_notebook.bat` | per-session launcher, Windows |
| `launch_notebook.command` | per-session launcher, macOS |
| `setup_mac.zsh` | one-time setup, macOS |

Everything the notebook calls lives in `LidarChangeScripts/`, one module per
topic:

| Module | |
|---|---|
| `__init__` | load GDAL before CloudComPy can shadow its DLLs |
| `environment_setup` | DLL load order, project directories |
| `path_utils` | interactive folder/file pickers |
| `pdal_runner` | running PDAL, progress reporting, pipeline execution |
| `crs_utils` | describing, converting and prompting for a CRS |
| `las_metadata` | LAS headers, dataset CRS, point counts, AOI overlap |
| `point_density` | calculate ground point density over AOI |
| `survey_dates` | convert GPS time to calendar dates |
| `preprocessing` | building and running the preprocessing pipeline |
| `preprocess_cache` | validating and reusing the preprocessed clouds |
| `boundary_utils` | AOI shapefiles and polygon geometry |
| `tile_grid` | the tile naming convention shared by the tiling steps |
| `tiling` | tiling and archiving |
| `tile_buffering` | add buffers to tiles |
| `tile_merging` | merge undersized tiles into neighbors |
| `alignment` | ICP alignment of each tile pair |
| `m3c2_utils` | write M3C2 parameter files |
| `m3c2_processing` | compute M3C2 change |
| `cloudcompy_utils` | main per-tile-pair processing loop |
| `dem_utils` | DEMs, hole filling, slope and hillshade |
| `rasterization` | gridding the M3C2 cloud and merging raster tiles |
| `visualization` | maps and M3C2 change figures |
| `swath_profile` | interactive point cloud cross-section picker |
| `run_record` | record parameters and versions per run |

`Inputs/`, `Outputs_*/`, `Parameters_*/`, `Preprocessed/` and `CloudComPy312/`
are generated or downloaded, and are not tracked.

## Built on

[PDAL](https://pdal.io/) for point cloud processing,
[CloudComPy](https://github.com/CloudCompare/CloudComPy) for ICP and M3C2,
and [GDAL](https://gdal.org/) for raster output.

The primary point cloud change detection processing uses the M3C2 method:

> Lague, D., Brodu, N., & Leroux, J., 2013. Accurate 3D comparison of complex
> topography with terrestrial laser scanner: Application to the Rangitikei
> canyon (N-Z). *ISPRS Journal of Photogrammetry and Remote Sensing* 82,
> p. 10–26, https://doi.org/10.1016/j.isprsjprs.2013.04.009

The general workflow (ICP alignment, filtered M3C2 approach, and tilted point profile) is based on:

> DiBiase, R.A., and Lamb, M.P., 2020. Dry sediment loading of headwater
> channels fuels post-wildfire debris flows in bedrock landscapes,
> *Geology* 48, p. 189-193, https://doi.org/10.1130/G46847.1

## Note on AI assistance

This project was developed with assistance from Anthropic's Claude Code. Code
generated or modified with Claude Code was reviewed and tested by the authors,
who are responsible for the final product.
