"""Generate maps of the before/after topography and M3C2 change for the
notebook visualization cell (and the swath profile cell).

Topography is drawn as a slopeshade with slope partially transparent over
hillshade. M3C2 change is drawn over it in discrete color bins set by
M3C2_COLOR_BREAKS defined in notebook.
"""
import numpy as np

from matplotlib.patches import Patch
from osgeo import gdal


def read_raster_as_array(path, max_size=4000):
    """Read the first band of a raster for plotting, at reduced resolution
    if larger than max_size pixels on its longest side.

    Returns (array, (xmin, xmax, ymin, ymax)); nodata pixels are NaN.
    """
    dataset = gdal.Open(str(path))
    band = dataset.GetRasterBand(1)

    shrink = max(dataset.RasterXSize, dataset.RasterYSize) / max_size
    if shrink > 1:
        array = band.ReadAsArray(
            buf_xsize=max(1, round(dataset.RasterXSize / shrink)),
            buf_ysize=max(1, round(dataset.RasterYSize / shrink))
        )
    else:
        array = band.ReadAsArray()

    array = array.astype(np.float32)
    nodata = band.GetNoDataValue()

    if nodata is not None:
        array = np.where(array == nodata, np.nan, array)

    gt = dataset.GetGeoTransform()
    xmin = gt[0]
    xmax = gt[0] + dataset.RasterXSize * gt[1]
    ymax = gt[3]
    ymin = gt[3] + dataset.RasterYSize * gt[5]

    dataset = None

    return array, (xmin, xmax, ymin, ymax)


def build_m3c2_color_bins(breaks, erosion_color="red"):
    """Build color bins from sorted M3C2 color-scale breaks.

    Any number of breaks is supported. A bin whose range straddles zero
    (i.e. isn't entirely negative or entirely positive) is transparent.
    Bins entirely negative or entirely positive are shaded from light
    (closest to zero) to dark (most extreme) in the "erosion_color"
    family (negative values) or the other family (positive values).
    """
    if erosion_color not in ("red", "blue"):
        raise ValueError(f"erosion_color must be 'red' or 'blue', got {erosion_color!r}")

    breaks = sorted(breaks)
    if not breaks:
        raise ValueError("M3C2_COLOR_BREAKS must contain at least one break value")

    edges = [-np.inf] + breaks + [np.inf]
    negative_family = erosion_color
    positive_family = "blue" if erosion_color == "red" else "red"

    light = {"red": np.array([1.0, 0.75, 0.80]), "blue": np.array([0.68, 0.85, 0.90])}
    dark = {"red": np.array([0.55, 0.0, 0.0]), "blue": np.array([0.0, 0.0, 0.55])}

    def shade(family, t):
        rgb = light[family] + (dark[family] - light[family]) * t
        return (float(rgb[0]), float(rgb[1]), float(rgb[2]), 1.0)

    all_edges = list(zip(edges[:-1], edges[1:]))
    negative_edges = [(lo, hi) for lo, hi in all_edges if hi <= 0]
    positive_edges = [(lo, hi) for lo, hi in all_edges if lo >= 0]

    bins = []

    n_neg = len(negative_edges)
    for i, (lo, hi) in enumerate(negative_edges):
        # i=0 is the most-negative (farthest from zero) bin -> darkest
        t = 1.0 if n_neg == 1 else 1.0 - i / (n_neg - 1)
        bins.append((lo, hi, shade(negative_family, t)))

    n_pos = len(positive_edges)
    for i, (lo, hi) in enumerate(positive_edges):
        # i=0 is the closest-to-zero bin -> lightest
        t = 1.0 if n_pos == 1 else i / (n_pos - 1)
        bins.append((lo, hi, shade(positive_family, t)))

    transparent = (0.0, 0.0, 0.0, 0.0)
    for lo, hi in all_edges:
        if not (hi <= 0 or lo >= 0):
            bins.append((lo, hi, transparent))

    return bins


def m3c2_to_rgba(values, color_bins):
    """Color an M3C2 array with color_bins (from build_m3c2_color_bins)."""
    rgba = np.zeros(values.shape + (4,), dtype=np.float32)
    for lo, hi, color in color_bins:
        rgba[(values > lo) & (values <= hi)] = color
    # NaN (nodata) pixels stay at the zero-initialized fully-transparent value.
    return rgba


def m3c2_legend_elements(color_bins):
    """Legend patches for color_bins, one per colored (not transparent) bin."""
    elements = []
    for lo, hi, color in color_bins:
        if color[3] == 0.0:
            continue  # skip the transparent "no significant change" bin
        if not np.isfinite(lo):
            label = f"< {hi:g} m"
        elif not np.isfinite(hi):
            label = f"> {lo:g} m"
        else:
            label = f"{lo:g} to {hi:g} m"
        elements.append(Patch(facecolor=color, label=label))
    return elements


def plot_slopeshade(ax, hillshade_path, slope_path, title):
    """Draw a hillshade with a semi-transparent slope layer on top."""
    hillshade, hillshade_extent = read_raster_as_array(hillshade_path)
    slope, slope_extent = read_raster_as_array(slope_path)

    # Linear 0-90 degree stretch, 0 = white, 90 = black
    slope_norm = np.clip(slope / 90, 0, 1)

    ax.imshow(hillshade, cmap="gray", extent=hillshade_extent)
    ax.imshow(slope_norm, cmap="gray_r", vmin=0, vmax=1, alpha=0.3, extent=slope_extent)

    ax.set_title(title)
    ax.set_xlabel("Easting (m)")
    ax.set_ylabel("Northing (m)")
    ax.set_aspect("equal")

    # Full coordinates on the axes (not "+3.819e6"-style offsets)
    ax.ticklabel_format(useOffset=False, style="plain")


def plot_m3c2_overlay(ax, m3c2, m3c2_extent, color_bins, legend_title):
    """Draw the M3C2 change raster over a map already on ax, with a legend."""
    ax.imshow(m3c2_to_rgba(m3c2, color_bins), extent=m3c2_extent)
    ax.legend(handles=m3c2_legend_elements(color_bins), loc="lower right", title=legend_title)


def change_map_drawer(rasters_dir, m3c2, m3c2_extent, color_bins, change_label):
    """Draw the AFTER slopeshade with the M3C2 change overlay on ax.
    """
    def draw_change_map(ax):
        plot_slopeshade(
            ax,
            rasters_dir / "after_hillshade.tif",
            rasters_dir / "after_slope.tif",
            f"AFTER Slopeshade with {change_label} Overlay"
        )
        plot_m3c2_overlay(ax, m3c2, m3c2_extent, color_bins, change_label)

    return draw_change_map


def save_maps_with_matching_crop(figures_and_paths, reference, dpi=200):
    """Save several maps of the same area with exactly the same crop."""
    reference.canvas.draw()
    crop = reference.get_tightbbox(reference.canvas.get_renderer()).padded(0.1)

    for figure, path in figures_and_paths:
        figure.savefig(path, dpi=dpi, facecolor="white", bbox_inches=crop)
