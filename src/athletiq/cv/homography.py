"""Homography estimation + Huber-robust refinement (paper §5.4).

We expose two entry points:

1. ``estimate_initial_homography(image_pts, pitch_pts)`` — the initial
   H_0 from detected keypoint correspondences (DLT via OpenCV).
2. ``refine_homography_huber(...)`` — the optimization-based voter from
   Eq. 12, implemented as an IRLS (iteratively re-weighted least squares)
   minimisation of the Huber loss over the reprojection residuals.

The Pixel-NeRF refinement from §5.4.2 is a v2 seam; the classical voter
already provides a very robust estimate for unmarked pitches when the
keypoint detector supplies enough correspondences.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
from scipy.optimize import least_squares

try:  # opencv is a core dep, but guard the import for docs/type-check envs
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None  # type: ignore[assignment]

FloatArray = npt.NDArray[np.floating]


@dataclass(frozen=True, slots=True)
class PitchKeypoints:
    """A set of image <-> pitch correspondences."""

    image_pts: FloatArray  # (N, 2) pixel coordinates
    pitch_pts: FloatArray  # (N, 2) pitch coordinates in metres
    labels: list[str] | None = None

    def __post_init__(self) -> None:
        img = np.asarray(self.image_pts)
        pit = np.asarray(self.pitch_pts)
        if img.shape != pit.shape or img.shape[-1] != 2:
            raise ValueError("image_pts and pitch_pts must have identical (N, 2) shape")
        if img.shape[0] < 4:
            raise ValueError("need at least 4 correspondences for a homography")


def estimate_initial_homography(kp: PitchKeypoints, use_ransac: bool = False) -> FloatArray:
    """Initial H_0 from direct linear transform (optionally RANSAC-robust)."""
    H, _ = _estimate_homography_with_mask(kp, use_ransac=use_ransac)
    return H


def _estimate_homography_with_mask(
    kp: PitchKeypoints, use_ransac: bool, ransac_threshold: float = 3.0
) -> tuple[FloatArray, FloatArray | None]:
    if cv2 is None:
        raise RuntimeError("opencv is required for homography estimation")
    method = cv2.RANSAC if use_ransac else 0
    H, mask = cv2.findHomography(
        kp.image_pts.astype(np.float32),
        kp.pitch_pts.astype(np.float32),
        method=method,
        ransacReprojThreshold=ransac_threshold,
    )
    if H is None:
        raise RuntimeError("DLT failed to find a homography — check correspondences")
    inlier_mask = None if mask is None else mask.flatten().astype(bool)
    return H.astype(np.float64), inlier_mask


def project_pixel_to_pitch(H: FloatArray, pixel_xy: FloatArray) -> FloatArray:
    """Apply a homography H to pixel points. Supports shape (2,) or (N, 2)."""
    pts = np.asarray(pixel_xy, dtype=np.float64)
    single = pts.ndim == 1
    if single:
        pts = pts.reshape(1, 2)
    ones = np.ones((pts.shape[0], 1), dtype=np.float64)
    homo = np.hstack([pts, ones])
    proj = homo @ H.T
    proj = proj[:, :2] / np.clip(proj[:, 2:3], a_min=1e-9, a_max=None)
    return proj[0] if single else proj


def refine_homography_huber(
    kp: PitchKeypoints,
    H_init: FloatArray | None = None,
    delta: float = 1.0,
    n_iters: int = 50,
    tol: float = 1e-8,
) -> FloatArray:
    """Eq. 12 — minimize Huber(|| H p_img - p_pitch ||) on geometric residuals.

    Uses non-linear least squares with a proper Huber loss applied to the
    per-correspondence reprojection errors (metres). The 8 degrees of freedom
    of H are parameterised by fixing H[2, 2] = 1. ``delta`` sets the L2->L1
    transition in metres (1 m is a reasonable default for broadcast footage).

    The initial estimate defaults to RANSAC DLT, which already rejects gross
    outliers; Huber then polishes the inlier fit to a sub-pixel/sub-cm level.
    """
    if cv2 is None:
        raise RuntimeError("opencv is required for homography refinement")

    if H_init is None:
        H0, mask = _estimate_homography_with_mask(kp, use_ransac=True)
    else:
        H0, mask = np.asarray(H_init, np.float64), None

    if abs(H0[2, 2]) < 1e-12:
        raise RuntimeError("degenerate initial homography (H[2,2] ~ 0)")
    H0 = H0 / H0[2, 2]
    params0 = H0.flatten()[:8]

    # If RANSAC identified inliers, refine only on them (hard rejection of
    # gross outliers). Otherwise fall back to the full set and let Huber
    # handle moderate noise via robust loss weighting.
    if mask is not None and mask.sum() >= 4:
        img = kp.image_pts[mask].astype(np.float64)
        pit = kp.pitch_pts[mask].astype(np.float64)
    else:
        img = kp.image_pts.astype(np.float64)
        pit = kp.pitch_pts.astype(np.float64)

    def residuals(params: FloatArray) -> FloatArray:
        H = np.empty(9, dtype=np.float64)
        H[:8] = params
        H[8] = 1.0
        H = H.reshape(3, 3)
        proj = project_pixel_to_pitch(H, img)
        return (proj - pit).ravel()  # 2N residuals, scipy applies Huber loss

    result = least_squares(
        residuals,
        params0,
        loss="huber",
        f_scale=delta,
        max_nfev=n_iters * 10,
        xtol=tol,
        ftol=tol,
    )
    H_out = np.empty(9, dtype=np.float64)
    H_out[:8] = result.x
    H_out[8] = 1.0
    return H_out.reshape(3, 3)
