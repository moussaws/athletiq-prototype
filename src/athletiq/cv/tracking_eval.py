"""Multi-object tracking evaluation — HOTA, MOTA, IDF1, ID-switches.

Implements the HOTA family (Luiten et al., IJCV 2021) at a single IoU
threshold α (default 0.5), plus classic CLEAR-MOT (MOTA) and identity
F1 (IDF1) so tracking quality on a labelled sample can be quoted with
one number.

HOTA_α = sqrt(DetA_α · AssA_α), where

    DetA_α = |TP| / (|TP| + |FN| + |FP|)

    AssA_α = (1 / |TP|) · Σ_c TPA(c) / (TPA(c) + FNA(c) + FPA(c))

A single frame is a list of axis-aligned boxes keyed by an integer
track id. Ground-truth and prediction sequences need only the union of
frames — missing frames are treated as empty.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import numpy.typing as npt
from scipy.optimize import linear_sum_assignment

FloatArray = npt.NDArray[np.floating]


@dataclass(frozen=True, slots=True)
class MOTBox:
    track_id: int
    xyxy: tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class MOTFrame:
    frame: int
    boxes: tuple[MOTBox, ...]


@dataclass(frozen=True, slots=True)
class HOTAScore:
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
    matched_pairs: dict[tuple[int, int], int] = field(default_factory=dict)


def iou_xyxy(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0.0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    if union <= 0.0:
        return 0.0
    return float(inter / union)


def _group_by_frame(frames: Iterable[MOTFrame]) -> dict[int, MOTFrame]:
    return {f.frame: f for f in frames}


def _match_frame(
    gt_boxes: tuple[MOTBox, ...],
    pred_boxes: tuple[MOTBox, ...],
    iou_thresh: float,
) -> list[tuple[int, int, float]]:
    """Hungarian match one frame; return list of (gt_idx, pred_idx, iou)."""
    if not gt_boxes or not pred_boxes:
        return []
    m, n = len(gt_boxes), len(pred_boxes)
    iou_mat = np.zeros((m, n), dtype=np.float64)
    for i, g in enumerate(gt_boxes):
        for j, p in enumerate(pred_boxes):
            iou_mat[i, j] = iou_xyxy(g.xyxy, p.xyxy)
    # maximise IoU → minimise -IoU
    r, c = linear_sum_assignment(-iou_mat)
    out: list[tuple[int, int, float]] = []
    for i, j in zip(r, c, strict=False):
        if iou_mat[i, j] >= iou_thresh:
            out.append((int(i), int(j), float(iou_mat[i, j])))
    return out


def compute_hota(
    ground_truth: Iterable[MOTFrame],
    predictions: Iterable[MOTFrame],
    iou_thresh: float = 0.5,
) -> HOTAScore:
    """Compute HOTA + CLEAR-MOT metrics at a single IoU threshold α.

    Perfect tracking (predictions == ground_truth) yields HOTA = 1.0.
    An ID-swap preserves detection accuracy but drops association accuracy.
    """
    gt_by_frame = _group_by_frame(ground_truth)
    pred_by_frame = _group_by_frame(predictions)
    all_frames = sorted(set(gt_by_frame) | set(pred_by_frame))

    tp = 0
    fp = 0
    fn = 0
    id_switches = 0

    # per-pair counts for AssA
    tpa: dict[tuple[int, int], int] = {}
    gt_freq: dict[int, int] = {}
    pred_freq: dict[int, int] = {}

    # IDF1 bookkeeping: gt-track total length, pred-track total length
    prev_gt_to_pred: dict[int, int] = {}

    gt_boxes_total = 0
    pred_boxes_total = 0

    for f in all_frames:
        gframe = gt_by_frame.get(f, MOTFrame(frame=f, boxes=tuple()))
        pframe = pred_by_frame.get(f, MOTFrame(frame=f, boxes=tuple()))
        gt_boxes_total += len(gframe.boxes)
        pred_boxes_total += len(pframe.boxes)
        for b in gframe.boxes:
            gt_freq[b.track_id] = gt_freq.get(b.track_id, 0) + 1
        for b in pframe.boxes:
            pred_freq[b.track_id] = pred_freq.get(b.track_id, 0) + 1

        matches = _match_frame(gframe.boxes, pframe.boxes, iou_thresh)
        matched_gt_idx = {gi for gi, _, _ in matches}
        matched_pred_idx = {pi for _, pi, _ in matches}

        tp += len(matches)
        fp += len(pframe.boxes) - len(matched_pred_idx)
        fn += len(gframe.boxes) - len(matched_gt_idx)

        new_gt_to_pred: dict[int, int] = {}
        for gi, pi, _ in matches:
            g_id = gframe.boxes[gi].track_id
            p_id = pframe.boxes[pi].track_id
            key = (g_id, p_id)
            tpa[key] = tpa.get(key, 0) + 1
            new_gt_to_pred[g_id] = p_id
            if g_id in prev_gt_to_pred and prev_gt_to_pred[g_id] != p_id:
                id_switches += 1
        prev_gt_to_pred = new_gt_to_pred

    if tp == 0:
        deta = 0.0
        assa = 0.0
    else:
        deta = tp / (tp + fn + fp)
        assa_acc = 0.0
        for (g_id, p_id), tpa_c in tpa.items():
            fna_c = gt_freq[g_id] - tpa_c
            fpa_c = pred_freq[p_id] - tpa_c
            denom = tpa_c + fna_c + fpa_c
            if denom > 0:
                # every matched detection with this (g,p) pair contributes
                assa_acc += (tpa_c * tpa_c) / denom
        assa = assa_acc / tp

    hota = float(np.sqrt(max(deta, 0.0) * max(assa, 0.0)))

    # CLEAR-MOT: MOTA = 1 - (FN + FP + IDSW) / |GT|
    gt_total = gt_boxes_total
    mota = 1.0 - (fn + fp + id_switches) / gt_total if gt_total > 0 else 0.0

    # IDF1 via bipartite matching on per-pair overlap
    idf1 = _idf1_from_pairs(tpa, gt_freq, pred_freq)

    return HOTAScore(
        hota=hota,
        deta=deta,
        assa=assa,
        mota=mota,
        idf1=idf1,
        alpha=iou_thresh,
        tp=tp,
        fp=fp,
        fn=fn,
        id_switches=id_switches,
        gt_boxes=gt_boxes_total,
        pred_boxes=pred_boxes_total,
        matched_pairs=dict(tpa),
    )


def _idf1_from_pairs(
    tpa: dict[tuple[int, int], int],
    gt_freq: dict[int, int],
    pred_freq: dict[int, int],
) -> float:
    if not tpa:
        return 0.0
    gt_ids = sorted(gt_freq)
    pred_ids = sorted(pred_freq)
    m, n = len(gt_ids), len(pred_ids)
    # maximise matched frames
    cost = np.zeros((m, n), dtype=np.float64)
    for i, g in enumerate(gt_ids):
        for j, p in enumerate(pred_ids):
            cost[i, j] = -float(tpa.get((g, p), 0))
    r, c = linear_sum_assignment(cost)
    idtp = sum(-cost[i, j] for i, j in zip(r, c, strict=False))
    idfn = sum(gt_freq.values()) - idtp
    idfp = sum(pred_freq.values()) - idtp
    denom = 2 * idtp + idfp + idfn
    return float(2 * idtp / denom) if denom > 0 else 0.0


def load_motchallenge(path: str | Path) -> list[MOTFrame]:
    """Load MOTChallenge CSV format: frame, id, x, y, w, h, conf, ...

    ``frame`` and ``id`` are 1-indexed in the spec; we preserve them as-is.
    Lines starting with '#' are ignored.
    """
    by_frame: dict[int, list[MOTBox]] = {}
    with Path(path).open("r", newline="") as fh:
        reader = csv.reader(fh)
        for row in reader:
            if not row or row[0].startswith("#"):
                continue
            frame = int(float(row[0]))
            tid = int(float(row[1]))
            x, y, w, h = (float(v) for v in row[2:6])
            by_frame.setdefault(frame, []).append(
                MOTBox(track_id=tid, xyxy=(x, y, x + w, y + h))
            )
    return [MOTFrame(frame=f, boxes=tuple(b)) for f, b in sorted(by_frame.items())]


def tracked_detections_to_frames(detections: Iterable[object]) -> list[MOTFrame]:
    """Convert CV pipeline ``TrackedDetection`` records into ``MOTFrame``s."""
    by_frame: dict[int, list[MOTBox]] = {}
    for d in detections:
        by_frame.setdefault(int(d.frame), []).append(  # type: ignore[attr-defined]
            MOTBox(
                track_id=int(d.track_id),  # type: ignore[attr-defined]
                xyxy=tuple(float(v) for v in d.bbox_xyxy),  # type: ignore[attr-defined]
            )
        )
    return [MOTFrame(frame=f, boxes=tuple(b)) for f, b in sorted(by_frame.items())]
