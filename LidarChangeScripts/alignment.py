"""ICP alignment of before/after tile pair.

BEFORE tile is the reference, AFTER tile is aligned

"""


import time
from collections import defaultdict

import numpy as np

import cloudComPy as cc


def _load_cloud(path, shift):
    """Load point cloud with an explicit global shift"""
    cloud = cc.loadPointCloud(
        str(path),
        mode=cc.CC_SHIFT_MODE.XYZ,
        x=shift[0],
        y=shift[1],
        z=shift[2]
    )

    if cloud is None:
        raise RuntimeError(f"CloudComPy could not load point cloud: {path}")

    return cloud


def align_tile_pair(before_buffered_file, after_buffered_file, after_core_file, min_spacing, shift,
                    min_rms_decrease=1e-5, sampling_limit=500000, timings=None):
    """Load a buffered BEFORE/AFTER tile pair plus the AFTER tile's
    (unbuffered) core points, spatially subsample all three to min_spacing,
    and ICP-align the AFTER cloud to the BEFORE cloud.

    The buffered clouds are used for DEM generation and M3C2 calculation
    to avoid edge effects. The core cloud is used for the M3C2 core points
    so that adjacent output tiles do not overlap.

    shift = (x, y, z) is the global shift added to every coordinate on
    load (e.g. minus the tile's lower-left corner).

    min_rms_decrease is ICP's stopping rule: it keeps iterating until the
    RMS between the clouds improves by less than this (m) from one
    iteration to the next.

    sampling_limit caps how many points ICP uses per iteration: a cloud
    with more points than this is randomly subsampled down to it.

    timings, if given, is a dict that gets the seconds spent on
    "load + subsample" and "ICP" added to it.
    """
    if timings is None:
        timings = defaultdict(float)

    start = time.perf_counter()

    before_cloud = _load_cloud(before_buffered_file, shift)
    after_cloud = _load_cloud(after_buffered_file, shift)
    core_cloud = _load_cloud(after_core_file, shift)

    # Double check that global shift is the same for all clouds
    shifts = {tuple(cloud.getGlobalShift()) for cloud in (before_cloud, after_cloud, core_cloud)}
    if len(shifts) != 1:
        raise RuntimeError(
            f"Point clouds were loaded with different global shifts {shifts}; "
            f"expected all to use {shift}"
        )

    # Delete scalar fields to reduce output file sizes for M3C2 clouds
    cc.ccPointCloud.deleteAllScalarFields(before_cloud)
    cc.ccPointCloud.deleteAllScalarFields(after_cloud)
    cc.ccPointCloud.deleteAllScalarFields(core_cloud)

    # Resample point clouds using minimum space method
    ref1 = cc.CloudSamplingTools.resampleCloudSpatially(before_cloud, min_spacing)
    before_sub, _ = before_cloud.partialClone(ref1)

    ref2 = cc.CloudSamplingTools.resampleCloudSpatially(after_cloud, min_spacing)
    after_sub, _ = after_cloud.partialClone(ref2)

    ref3 = cc.CloudSamplingTools.resampleCloudSpatially(core_cloud, min_spacing)
    core_sub, _ = core_cloud.partialClone(ref3)

    # Delete original clouds
    cc.deleteEntity(before_cloud)
    cc.deleteEntity(after_cloud)
    cc.deleteEntity(core_cloud)

    # Resampled point cloud sizes
    print(f"Before points (buffered): {before_sub.size():,}")
    print(f"After points (buffered): {after_sub.size():,}")
    print(f"Core points (this tile): {core_sub.size():,}")

    # Report time to load and subsample tile
    timings["load + subsample"] += time.perf_counter() - start
    start = time.perf_counter()

    # Determine ICP alignment using MAX_ERROR_CONVERGENCE method
    # (iterate until the RMS improves by less than minRMSDecrease between steps)
    icp_result = cc.ICP(
        data=after_sub,
        model=before_sub,
        minRMSDecrease=min_rms_decrease,
        method=cc.CONVERGENCE_TYPE.MAX_ERROR_CONVERGENCE,
        randomSamplingLimit=sampling_limit
    )

    # Apply transformation to AFTER tiles (buffered and core)
    after_sub.applyRigidTransformation(icp_result.transMat)
    core_sub.applyRigidTransformation(icp_result.transMat)

    # Save ICP transformation matrix for later use
    icp_matrix = np.array(icp_result.transMat.data(), dtype=float).reshape(4, 4).T

    timings["ICP"] += time.perf_counter() - start

    print(f"ICP complete (final RMS {icp_result.finalRMS:.3f} m)")

    return before_sub, after_sub, core_sub, icp_matrix
