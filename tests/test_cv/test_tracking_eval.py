"""Unit tests for the HOTA / MOTA / IDF1 tracking-eval module."""

from __future__ import annotations

from pathlib import Path

import pytest

from athletiq.cv.tracking_eval import (
    MOTBox,
    MOTFrame,
    compute_hota,
    iou_xyxy,
    load_motchallenge,
)


def _linear_track(
    track_id: int,
    start: tuple[float, float],
    velocity: tuple[float, float],
    n_frames: int,
    box_wh: tuple[float, float] = (50.0, 100.0),
) -> list[tuple[int, MOTBox]]:
    out = []
    x0, y0 = start
    vx, vy = velocity
    w, h = box_wh
    for f in range(n_frames):
        cx = x0 + vx * f
        cy = y0 + vy * f
        out.append(
            (
                f,
                MOTBox(
                    track_id=track_id,
                    xyxy=(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2),
                ),
            )
        )
    return out


def _frames_from_boxes(pairs: list[tuple[int, MOTBox]]) -> list[MOTFrame]:
    by_frame: dict[int, list[MOTBox]] = {}
    for f, b in pairs:
        by_frame.setdefault(f, []).append(b)
    return [MOTFrame(frame=f, boxes=tuple(b)) for f, b in sorted(by_frame.items())]


def test_iou_perfect_overlap_and_disjoint() -> None:
    a = (0.0, 0.0, 10.0, 10.0)
    assert iou_xyxy(a, a) == pytest.approx(1.0)
    assert iou_xyxy(a, (100.0, 100.0, 110.0, 110.0)) == pytest.approx(0.0)
    assert iou_xyxy(a, (5.0, 5.0, 15.0, 15.0)) == pytest.approx(25.0 / 175.0)


def test_hota_is_one_for_perfect_tracking() -> None:
    t1 = _linear_track(1, (100.0, 200.0), (10.0, 0.0), 20)
    t2 = _linear_track(2, (400.0, 300.0), (-5.0, 5.0), 20)
    gt = _frames_from_boxes(t1 + t2)
    pred = _frames_from_boxes(t1 + t2)
    score = compute_hota(gt, pred, iou_thresh=0.5)
    assert score.hota == pytest.approx(1.0)
    assert score.deta == pytest.approx(1.0)
    assert score.assa == pytest.approx(1.0)
    assert score.mota == pytest.approx(1.0)
    assert score.idf1 == pytest.approx(1.0)
    assert score.id_switches == 0
    assert score.fp == 0 and score.fn == 0
    assert score.tp == 40  # 2 tracks × 20 frames


def test_id_swap_drops_associations_not_detections() -> None:
    # GT has tracks 1 and 2 for 20 frames. Pred swaps the IDs at frame 10.
    t1 = _linear_track(1, (100.0, 200.0), (10.0, 0.0), 20)
    t2 = _linear_track(2, (400.0, 300.0), (-5.0, 5.0), 20)
    gt = _frames_from_boxes(t1 + t2)

    swapped: list[tuple[int, MOTBox]] = []
    for f, b in t1:
        new_id = 1 if f < 10 else 2
        swapped.append((f, MOTBox(track_id=new_id, xyxy=b.xyxy)))
    for f, b in t2:
        new_id = 2 if f < 10 else 1
        swapped.append((f, MOTBox(track_id=new_id, xyxy=b.xyxy)))
    pred = _frames_from_boxes(swapped)

    score = compute_hota(gt, pred, iou_thresh=0.5)
    assert score.deta == pytest.approx(1.0)
    assert score.assa < 0.8
    assert score.hota < 1.0
    assert score.id_switches == 2
    # MOTA penalises ID switches in the numerator
    assert score.mota < 1.0


def test_missing_half_detections_halves_deta() -> None:
    t1 = _linear_track(1, (100.0, 200.0), (10.0, 0.0), 20)
    gt = _frames_from_boxes(t1)
    # prediction only in every other frame
    pred = _frames_from_boxes([(f, b) for f, b in t1 if f % 2 == 0])
    score = compute_hota(gt, pred, iou_thresh=0.5)
    assert score.tp == 10
    assert score.fn == 10
    assert score.fp == 0
    assert score.deta == pytest.approx(10.0 / (10 + 10 + 0))
    # FNAs halve AssA: TPA=10, FNA=10, FPA=0 → 10*10/20 per matched detection → 0.5 average
    assert score.assa == pytest.approx(0.5)
    assert score.idf1 == pytest.approx(2 * 10 / (2 * 10 + 0 + 10))


def test_extra_false_positive_track_drops_deta() -> None:
    t1 = _linear_track(1, (100.0, 200.0), (10.0, 0.0), 10)
    gt = _frames_from_boxes(t1)
    # add a ghost track that doesn't exist
    ghost = _linear_track(99, (800.0, 500.0), (0.0, 0.0), 10)
    pred = _frames_from_boxes(t1 + ghost)
    score = compute_hota(gt, pred, iou_thresh=0.5)
    assert score.tp == 10
    assert score.fp == 10
    assert score.fn == 0
    assert score.deta == pytest.approx(10.0 / (10 + 0 + 10))


def test_id_switch_counted_across_unmatched_gap() -> None:
    """A GT track that reappears under a different pred id after an
    unmatched frame must still count as an ID switch. Regression for a
    bug where prev_gt_to_pred was replaced (instead of updated) each
    frame, clearing the history during gaps."""
    # frame 0: gt#1 matched to pred#1
    # frame 1: no prediction for gt#1 (unmatched gap)
    # frame 2: gt#1 matched to pred#2  → this is an ID switch
    gt = [
        MOTFrame(frame=0, boxes=(MOTBox(track_id=1, xyxy=(0.0, 0.0, 50.0, 100.0)),)),
        MOTFrame(frame=1, boxes=(MOTBox(track_id=1, xyxy=(10.0, 0.0, 60.0, 100.0)),)),
        MOTFrame(frame=2, boxes=(MOTBox(track_id=1, xyxy=(20.0, 0.0, 70.0, 100.0)),)),
    ]
    pred = [
        MOTFrame(frame=0, boxes=(MOTBox(track_id=1, xyxy=(0.0, 0.0, 50.0, 100.0)),)),
        MOTFrame(frame=1, boxes=tuple()),
        MOTFrame(frame=2, boxes=(MOTBox(track_id=2, xyxy=(20.0, 0.0, 70.0, 100.0)),)),
    ]
    score = compute_hota(gt, pred, iou_thresh=0.5)
    assert score.id_switches == 1


def test_load_motchallenge_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "gt.txt"
    path.write_text(
        "\n".join(
            [
                "1,1,10,20,30,40,1,-1,-1,-1",
                "1,2,100,120,50,80,1,-1,-1,-1",
                "2,1,15,22,30,40,1,-1,-1,-1",
            ]
        )
    )
    frames = load_motchallenge(path)
    assert len(frames) == 2
    assert frames[0].frame == 1 and len(frames[0].boxes) == 2
    assert frames[0].boxes[0].xyxy == (10.0, 20.0, 40.0, 60.0)
    assert frames[1].boxes[0].track_id == 1
