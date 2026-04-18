"""Paper §5.4 — homography estimation + Huber-robust voter (Eq. 12)."""

from __future__ import annotations

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from athletiq.cv.homography import (  # noqa: E402
    PitchKeypoints,
    estimate_initial_homography,
    project_pixel_to_pitch,
    refine_homography_huber,
)


def _synthetic_keypoints(h_true: np.ndarray, n: int = 8, seed: int = 0) -> PitchKeypoints:
    rng = np.random.default_rng(seed)
    image_pts = rng.uniform(50, 1800, size=(n, 2))
    proj = project_pixel_to_pitch(h_true, image_pts)
    return PitchKeypoints(image_pts=image_pts, pitch_pts=proj)


def test_dlt_recovers_known_homography() -> None:
    H_true = np.array(
        [[0.06, 0.001, 2.0], [0.001, 0.06, 1.0], [0.0001, 0.0002, 1.0]], dtype=np.float64
    )
    kp = _synthetic_keypoints(H_true, n=8)
    H_est = estimate_initial_homography(kp)
    # compare as projections (scale ambiguity)
    sample = np.array([[100.0, 200.0], [800.0, 900.0]])
    truth = project_pixel_to_pitch(H_true, sample)
    est = project_pixel_to_pitch(H_est, sample)
    assert np.allclose(est, truth, atol=1e-3)


def test_huber_voter_robust_to_outliers() -> None:
    """With 3 of 12 correspondences corrupted, the Huber-refined H should
    still project probe points to within a small reprojection error."""
    H_true = np.array([[0.05, 0.0, 5.0], [0.0, 0.05, 3.0], [0.0, 0.0, 1.0]], dtype=np.float64)
    kp = _synthetic_keypoints(H_true, n=12, seed=3)
    pitch_pts = kp.pitch_pts.copy()
    pitch_pts[:3] += np.array([30.0, 20.0])  # pollute 25% of correspondences
    kp_noisy = PitchKeypoints(image_pts=kp.image_pts, pitch_pts=pitch_pts)

    H_ref = refine_homography_huber(kp_noisy, delta=1.0, n_iters=25)

    probes = np.array([[400.0, 500.0], [1200.0, 300.0], [800.0, 700.0]])
    truth = project_pixel_to_pitch(H_true, probes)
    proj = project_pixel_to_pitch(H_ref, probes)
    err = np.linalg.norm(proj - truth, axis=1).max()
    assert err < 0.5  # sub-50cm reprojection despite 25% outlier correspondences


def test_huber_voter_no_regression_on_clean_data() -> None:
    """On clean data, the refined H is ~indistinguishable from DLT."""
    H_true = np.array([[0.04, 0.001, 2.0], [0.0, 0.04, 1.0], [0.0, 0.0, 1.0]], dtype=np.float64)
    kp = _synthetic_keypoints(H_true, n=10, seed=7)
    H_ref = refine_homography_huber(kp, delta=1.0, n_iters=20)
    probe = np.array([[400.0, 500.0]])
    err = np.linalg.norm(
        project_pixel_to_pitch(H_ref, probe) - project_pixel_to_pitch(H_true, probe)
    )
    assert err < 1e-3


def test_project_supports_single_and_batch() -> None:
    H = np.eye(3)
    single = project_pixel_to_pitch(H, np.array([10.0, 20.0]))
    assert single.shape == (2,)
    batch = project_pixel_to_pitch(H, np.array([[10.0, 20.0], [30.0, 40.0]]))
    assert batch.shape == (2, 2)


def test_too_few_points_rejected() -> None:
    with pytest.raises(ValueError):
        PitchKeypoints(
            image_pts=np.zeros((3, 2)),
            pitch_pts=np.zeros((3, 2)),
        )
