"""Unit tests for the DynamicHomographyTracker (LK-based per-frame H)."""

from __future__ import annotations

import cv2
import numpy as np

from athletiq.cv.homography import (
    DynamicHomographyTracker,
    PitchKeypoints,
    project_pixel_to_pitch,
)


def _make_checkerboard(size: tuple[int, int] = (480, 720)) -> np.ndarray:
    """A highly textured frame LK can track reliably.

    We draw small high-contrast cross markers at each keypoint location so
    LK has strong 2D gradient there (a plain checkerboard corner between
    two tiles isn't always enough for pyramidal LK when keypoints sit
    exactly on a tile edge).
    """
    h, w = size
    img = np.full((h, w, 3), 128, dtype=np.uint8)
    # Random-ish texture so LK has something to lock onto elsewhere too
    rng = np.random.default_rng(0)
    noise = rng.integers(0, 60, size=(h, w, 3), dtype=np.int32)
    img = np.clip(img.astype(np.int32) + noise, 0, 255).astype(np.uint8)
    for cx, cy in [(100, 100), (620, 100), (620, 380), (100, 380), (360, 240)]:
        cv2.line(img, (cx - 12, cy), (cx + 12, cy), (255, 255, 255), 2)
        cv2.line(img, (cx, cy - 12), (cx, cy + 12), (255, 255, 255), 2)
        cv2.line(img, (cx - 8, cy - 8), (cx + 8, cy + 8), (0, 0, 0), 2)
        cv2.line(img, (cx - 8, cy + 8), (cx + 8, cy - 8), (0, 0, 0), 2)
    return img


def _translate(img: np.ndarray, dx: int, dy: int) -> np.ndarray:
    M = np.array([[1, 0, dx], [0, 1, dy]], dtype=np.float32)
    h, w = img.shape[:2]
    return cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_REPLICATE)


def _default_kp() -> PitchKeypoints:
    image_pts = np.array([[100, 100], [620, 100], [620, 380], [100, 380]], dtype=np.float64)
    pitch_pts = np.array([[0, 68], [105, 68], [105, 0], [0, 0]], dtype=np.float64)
    return PitchKeypoints(image_pts=image_pts, pitch_pts=pitch_pts)


def test_static_scene_keeps_homography_stable() -> None:
    kp = _default_kp()
    tracker = DynamicHomographyTracker(kp)
    frame = _make_checkerboard()
    tracker.prime(frame)
    H0 = tracker.H.copy()
    for _ in range(5):
        tracker.update(frame)
    # No camera motion → H should barely change
    assert tracker.n_active == 4
    np.testing.assert_allclose(tracker.H, H0, atol=1e-3)


def test_pan_shift_updates_homography_so_projection_stays_consistent() -> None:
    kp = _default_kp()
    tracker = DynamicHomographyTracker(kp)
    frame0 = _make_checkerboard()
    tracker.prime(frame0)
    H0 = tracker.H.copy()

    # Where does the pixel at the centre of the pitch corners currently project to?
    centre_px0 = np.mean(kp.image_pts, axis=0)
    centre_pitch_static = project_pixel_to_pitch(H0, centre_px0)

    # Simulate a camera pan: image content shifts by +30 px horizontally.
    # Under a static H the same on-screen foot-point would project to a
    # different pitch location. With the dynamic tracker, the image keypoints
    # follow the content and the same *content* should project back to the
    # same pitch coords.
    dx, dy = 30, 0
    frame1 = _translate(frame0, dx, dy)
    tracker.update(frame1)

    # After LK, the image_pts should have moved by ~(dx, dy) and H should
    # be re-fit so that projecting the shifted centre-pixel still lands near
    # the same pitch coord.
    shifted_centre = centre_px0 + np.array([dx, dy])
    centre_pitch_dyn = project_pixel_to_pitch(tracker.H, shifted_centre)
    assert tracker.n_active >= 4
    np.testing.assert_allclose(centre_pitch_dyn, centre_pitch_static, atol=0.5)


def test_active_count_never_grows() -> None:
    kp = _default_kp()
    tracker = DynamicHomographyTracker(kp)
    frame = _make_checkerboard()
    tracker.prime(frame)
    assert tracker.n_active == 4
    for _ in range(3):
        tracker.update(frame)
        # LK can only lose keypoints, never add them
        assert tracker.n_active <= 4


def test_tracker_coasts_below_four_active_keypoints() -> None:
    # Start with 5 keypoints, force-drop a couple, verify tracker doesn't crash.
    image_pts = np.array(
        [[100, 100], [620, 100], [620, 380], [100, 380], [360, 240]], dtype=np.float64
    )
    pitch_pts = np.array(
        [[0, 68], [105, 68], [105, 0], [0, 0], [52.5, 34]], dtype=np.float64
    )
    kp = PitchKeypoints(image_pts=image_pts, pitch_pts=pitch_pts)
    tracker = DynamicHomographyTracker(kp)
    frame = _make_checkerboard()
    tracker.prime(frame)
    # Big translation off-frame: LK usually loses most points
    far = _translate(frame, 600, 400)
    tracker.update(far)
    # Tracker should either have a valid H still or have coasted with the previous one
    assert tracker.H.shape == (3, 3)
    assert tracker.n_active >= 0
