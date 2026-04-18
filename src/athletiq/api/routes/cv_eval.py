"""Tracking-quality evaluation endpoints: HOTA + MOTA + IDF1."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from athletiq.cv.tracking_eval import (
    MOTFrame,
    compute_hota,
    load_motchallenge,
    tracked_detections_to_frames,
)

router = APIRouter()

_VIDEO_FILE = File(...)
_GT_FILE = File(...)
_MAX_FRAMES_FORM = Form(default=None)
_CONF_FORM = Form(default=0.25)
_IOU_FORM = Form(default=0.5)


class HOTAResponse(BaseModel):
    hota: float
    deta: float
    assa: float
    mota: float
    idf1: float
    alpha: float
    tp: int
    fp: int
    fn: int
    id_switches: int
    gt_boxes: int
    pred_boxes: int
    n_gt_tracks: int
    n_pred_tracks: int
    verdict: str


def _verdict(hota: float) -> str:
    if hota >= 0.85:
        return "Excellent tracking — detections + identities near-perfect."
    if hota >= 0.65:
        return "Good tracking — identities mostly stable across the clip."
    if hota >= 0.45:
        return "Fair tracking — noticeable ID switches or missed figures."
    if hota >= 0.25:
        return "Weak tracking — frequent ID swaps or dropped tracks."
    return "Poor tracking — identities unreliable on this clip."


def _count_unique_tracks(frames: list[MOTFrame]) -> int:
    return len({b.track_id for f in frames for b in f.boxes})


@router.post("/hota", response_model=HOTAResponse)
async def eval_hota(
    video: UploadFile = _VIDEO_FILE,
    gt: UploadFile = _GT_FILE,
    max_frames: int | None = _MAX_FRAMES_FORM,
    conf: float = _CONF_FORM,
    iou: float = _IOU_FORM,
) -> HOTAResponse:
    """Run CV pipeline on ``video`` and score against MOTChallenge-format ``gt``."""
    try:
        from athletiq.cv.pipeline import analyze_video
    except ImportError as e:  # pragma: no cover
        raise HTTPException(
            status_code=501,
            detail="CV extras not installed on the server. Install with `pip install -e '.[cv]'`.",
        ) from e

    with tempfile.NamedTemporaryFile(
        delete=False, suffix=Path(video.filename or "clip.mp4").suffix
    ) as tmp_v:
        tmp_v.write(await video.read())
        video_path = tmp_v.name
    with tempfile.NamedTemporaryFile(
        delete=False, suffix=Path(gt.filename or "gt.txt").suffix, mode="wb"
    ) as tmp_g:
        tmp_g.write(await gt.read())
        gt_path = tmp_g.name

    try:
        gt_frames = load_motchallenge(gt_path)
        if not gt_frames:
            raise HTTPException(status_code=422, detail="Ground-truth file parsed 0 frames.")
        result = analyze_video(video_path, conf=conf, max_frames=max_frames)
        pred_frames = tracked_detections_to_frames(result.detections)
        score = compute_hota(gt_frames, pred_frames, iou_thresh=iou)
    finally:
        Path(video_path).unlink(missing_ok=True)
        Path(gt_path).unlink(missing_ok=True)

    return HOTAResponse(
        hota=score.hota,
        deta=score.deta,
        assa=score.assa,
        mota=score.mota,
        idf1=score.idf1,
        alpha=score.alpha,
        tp=score.tp,
        fp=score.fp,
        fn=score.fn,
        id_switches=score.id_switches,
        gt_boxes=score.gt_boxes,
        pred_boxes=score.pred_boxes,
        n_gt_tracks=_count_unique_tracks(gt_frames),
        n_pred_tracks=_count_unique_tracks(pred_frames),
        verdict=_verdict(score.hota),
    )
