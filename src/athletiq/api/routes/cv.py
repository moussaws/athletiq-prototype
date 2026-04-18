"""CV pipeline endpoints: upload a video, get tracked detections + pitch coords."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from athletiq.cv.homography import PitchKeypoints

router = APIRouter()

_VIDEO_FILE = File(...)
_KEYPOINTS_FORM = Form(default="")
_MAX_FRAMES_FORM = Form(default=30)
_CONF_FORM = Form(default=0.25)


class CVCapabilityResponse(BaseModel):
    cv_available: bool
    reason: str | None = None


@router.get("/capabilities", response_model=CVCapabilityResponse)
def cv_capabilities() -> CVCapabilityResponse:
    """Report whether the torch/ultralytics extra is available in this install."""
    try:
        import supervision  # noqa: F401
        import torch  # noqa: F401
        import ultralytics  # noqa: F401
    except ImportError as e:
        return CVCapabilityResponse(cv_available=False, reason=str(e))
    return CVCapabilityResponse(cv_available=True)


class DetectionOut(BaseModel):
    frame: int
    track_id: int
    cls: int
    conf: float
    bbox_xyxy: list[float]
    foot_xy: list[float]
    pitch_xy: list[float] | None


class VideoAnalysisResponse(BaseModel):
    fps: float
    width: int
    height: int
    n_detections: int
    detections: list[DetectionOut]


@router.post("/analyze", response_model=VideoAnalysisResponse)
async def analyze(
    video: UploadFile = _VIDEO_FILE,
    keypoints_json: str = _KEYPOINTS_FORM,
    max_frames: int = _MAX_FRAMES_FORM,
    conf: float = _CONF_FORM,
) -> VideoAnalysisResponse:
    """Upload an MP4 and run YOLOv10 + ByteTrack (+ optional homography)."""
    try:
        from athletiq.cv.pipeline import analyze_video
    except ImportError as e:  # pragma: no cover
        raise HTTPException(
            status_code=501,
            detail=(
                "CV extras not installed on the server. Install with `pip install -e '.[cv]'`."
            ),
        ) from e

    keypoints: PitchKeypoints | None = None
    if keypoints_json:
        try:
            payload = json.loads(keypoints_json)
            img_pts = np.array(payload["image_pts"], dtype=np.float64)
            pitch_pts = np.array(payload["pitch_pts"], dtype=np.float64)
            keypoints = PitchKeypoints(image_pts=img_pts, pitch_pts=pitch_pts)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            raise HTTPException(status_code=422, detail=f"bad keypoints_json: {e}") from e

    with tempfile.NamedTemporaryFile(
        delete=False, suffix=Path(video.filename or "clip.mp4").suffix
    ) as tmp:
        data = await video.read()
        tmp.write(data)
        tmp_path = tmp.name

    try:
        result = analyze_video(
            tmp_path,
            keypoints=keypoints,
            conf=conf,
            max_frames=max_frames,
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return VideoAnalysisResponse(
        fps=result.fps,
        width=result.width,
        height=result.height,
        n_detections=len(result.detections),
        detections=[
            DetectionOut(
                frame=d.frame,
                track_id=d.track_id,
                cls=d.cls,
                conf=d.conf,
                bbox_xyxy=list(d.bbox_xyxy),
                foot_xy=list(d.foot_xy),
                pitch_xy=list(d.pitch_xy) if d.pitch_xy is not None else None,
            )
            for d in result.detections
        ],
    )
