"""Pillar C — computer vision infrastructure for rural deployment.

Implements Section 5 of the AthletIQ paper:

* YOLOv10 detection (ultralytics), fine-tuned on SoccerNet (pretrained in v1)
* ByteTrack multi-object tracking across frames
* Classical Hungarian-assignment Re-ID (IoU + spatial + optional embedding)
* Classical homography from semantic pitch keypoints + Huber-robust voter
  (Eq. 12) for stable pitch-metric projection

The heavier dependencies (``torch``, ``ultralytics``, ``supervision``) live in
the ``[cv]`` extra — imported lazily so the core analytics packages install
on any machine without a CUDA toolchain.
"""

from athletiq.cv.homography import (
    PitchKeypoints,
    estimate_initial_homography,
    project_pixel_to_pitch,
    refine_homography_huber,
)
from athletiq.cv.pipeline import VideoTrackingResult, analyze_video

__all__ = [
    "PitchKeypoints",
    "VideoTrackingResult",
    "analyze_video",
    "estimate_initial_homography",
    "project_pixel_to_pitch",
    "refine_homography_huber",
]
