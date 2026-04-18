"""End-to-end video -> tracks -> pitch-metric trajectories pipeline.

This is the "Phase 1 + 2" of Algorithm 1 in the paper:

    YOLOv10 detection -> ByteTrack tracking -> homography projection -> metric trajectories

The CV stack (torch, ultralytics, supervision) is imported lazily so the
core analytics packages install anywhere. If the optional deps are not
installed, ``analyze_video`` raises a clear ImportError with instructions.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import numpy.typing as npt

from athletiq.cv.homography import PitchKeypoints, project_pixel_to_pitch, refine_homography_huber

FloatArray = npt.NDArray[np.floating]


@dataclass(frozen=True, slots=True)
class TrackedDetection:
    frame: int
    track_id: int
    cls: int
    conf: float
    # image-space bbox in pixels (x1, y1, x2, y2)
    bbox_xyxy: tuple[float, float, float, float]
    # foot-point in pixel coords (for projection)
    foot_xy: tuple[float, float]
    # pitch-coord foot-point (metres) — populated after projection
    pitch_xy: tuple[float, float] | None = None


@dataclass
class VideoTrackingResult:
    detections: list[TrackedDetection] = field(default_factory=list)
    homography: FloatArray | None = None
    fps: float = 25.0
    width: int = 0
    height: int = 0

    def tracks_by_id(self) -> dict[int, list[TrackedDetection]]:
        out: dict[int, list[TrackedDetection]] = {}
        for d in self.detections:
            out.setdefault(d.track_id, []).append(d)
        for lst in out.values():
            lst.sort(key=lambda d: d.frame)
        return out


def _try_import_cv_stack() -> tuple[object, object]:
    try:
        import supervision as sv  # type: ignore
        from ultralytics import YOLO  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise ImportError(
            "CV extras not installed. Run `pip install -e '.[cv]'` to enable video "
            "analysis (installs torch, ultralytics, supervision)."
        ) from e
    return YOLO, sv


def analyze_video(
    video_path: str | Path,
    *,
    keypoints: PitchKeypoints | None = None,
    model_weights: str = "yolov10n.pt",
    device: str = "cpu",
    conf: float = 0.25,
    iou: float = 0.5,
    max_frames: int | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> VideoTrackingResult:
    """Run YOLOv10 + ByteTrack on a video and optionally project to pitch coords.

    Parameters
    ----------
    video_path : path to an MP4/AVI file.
    keypoints : optional pitch-corner / landmark correspondences. If provided,
        a Huber-refined homography is fit once on the first frame and used to
        project every detection's foot-point to pitch metres.
    model_weights : ultralytics model name or path. Defaults to the pretrained
        YOLOv10n (downloaded by ultralytics on first use).
    device : "cpu" / "cuda" / "mps".
    conf, iou : detection thresholds.
    max_frames : optional cap for quick demos.
    progress : optional callback (frame_idx, total).
    """
    YOLO, sv = _try_import_cv_stack()  # noqa: N806
    import cv2

    model = YOLO(model_weights)
    tracker = sv.ByteTrack()

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise FileNotFoundError(f"cannot open video: {video_path}")

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

    result = VideoTrackingResult(fps=fps, width=width, height=height)
    if keypoints is not None:
        result.homography = refine_homography_huber(keypoints)

    frame_idx = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if max_frames is not None and frame_idx >= max_frames:
                break

            yolo_out = model.predict(frame, conf=conf, iou=iou, device=device, verbose=False)[0]
            detections = sv.Detections.from_ultralytics(yolo_out)
            detections = tracker.update_with_detections(detections)

            # extract per-detection info
            if detections.tracker_id is None:
                frame_idx += 1
                continue

            for bbox, tid, cls, conf_i in zip(
                detections.xyxy,
                detections.tracker_id,
                detections.class_id if detections.class_id is not None else [0] * len(detections),
                detections.confidence
                if detections.confidence is not None
                else [0.0] * len(detections),
                strict=False,
            ):
                x1, y1, x2, y2 = (float(v) for v in bbox)
                foot = ((x1 + x2) / 2.0, y2)
                pitch_xy: tuple[float, float] | None = None
                if result.homography is not None:
                    p = project_pixel_to_pitch(result.homography, np.array(foot))
                    pitch_xy = (float(p[0]), float(p[1]))
                result.detections.append(
                    TrackedDetection(
                        frame=frame_idx,
                        track_id=int(tid),
                        cls=int(cls),
                        conf=float(conf_i),
                        bbox_xyxy=(x1, y1, x2, y2),
                        foot_xy=foot,
                        pitch_xy=pitch_xy,
                    )
                )

            if progress is not None:
                progress(frame_idx, total)
            frame_idx += 1
    finally:
        cap.release()
    return result
