# PR #4 Re-test Report — `/cv` page on real football broadcast

**PR**: [moussaws/athletiq-prototype#4](https://github.com/moussaws/athletiq-prototype/pull/4)
**Session**: https://app.devin.ai/sessions/e9df82d696244f1698b684f56e63506f
**Date**: 2026-04-18
**Round**: 2 of 2 (first round used a 4K pedestrian clip; user asked for real football)

## How I tested

One continuous end-to-end flow against the locally-running stack (FastAPI on
`:8000`, Next.js on `:3000`, CV extras installed: torch 2.11.0 CPU + ultralytics
8.4.38 + supervision 0.27.0.post2, YOLOv10n weights auto-downloaded to
`~/.cache/ultralytics`):

1. Home → click "Pillar C — CV pipeline" card → `/cv`.
2. Select `0bfacc_0.mp4` (DFL Bundesliga broadcast clip from Roboflow's
   `sports/examples/soccer/setup.sh`, originally a Kaggle CC-licensed dataset;
   19.9 MB, 1920×1080, 25 fps, 30 s).
3. Analyze with `max_frames=30`, `conf=0.25`, homography **off** — verify
   detections table.
4. Tick "Project foot-points to pitch coordinates", leave default keypoints
   (1920×1080 corners → 105×68 m pitch), analyze — verify pitch mini-map.

## Summary

All 3 adversarial assertions passed on real football footage.

## Results

| # | Assertion | Result | Evidence |
| - | --------- | ------ | -------- |
| T1 | Emerald "CV pipeline ready — YOLOv10 + ByteTrack" banner | **PASS** | [screenshot](#t1) |
| T2 | 257 detections, 14 unique tracks, Pitch(m)="—" when homography off | **PASS** | [screenshot](#t2) |
| T3 | 257 (100%) projected, mini-map shows players scattered inside 105×68 m pitch, Pitch(m) shows realistic decimals | **PASS** | [screenshot](#t3) |

## Escalations

None. Two observations worth noting (neither is a PR bug):

1. **The `projected N (P%)` stat counts "homography returned non-null", not
   "inside-pitch"** (same caveat as round 1). With the football clip that's
   semantically fine — the default keypoints map 1920×1080 corners to the
   105×68 m rectangle, so 100% projected = 100% mapped into something close to
   pitch coords, and visually most points *do* land inside the pitch.

2. **A few points project slightly outside the pitch rectangle** (e.g. track 5
   at `107.2, -0.3` — outside by 0.3 m on one axis). These are players whose
   foot-point in the image falls outside the `image_pts` rectangle
   `(100,100)-(1820,980)`. The backend returns the projected value anyway,
   which is correct behaviour — clipping should be the dashboard's
   responsibility if we want "inside-pitch only". Not in scope for PR #4.

## Screenshots

### <a id="t1"></a>T1 — Emerald capability banner

Header reads: `CV pipeline ready — YOLOv10 + ByteTrack (+ optional Huber-refined homography) available on the server.`

![T1 banner](https://app.devin.ai/attachments/ff61c8e1-42e2-4735-b640-7e604c546e04/pr4-football-t1-banner.png)

### <a id="t2"></a>T2 — Detections table populated, no homography

Stats strip: `fps 25.0 · resolution 1920×1080 · detections 257 · unique tracks 14 · projected 0 (0%)`. Table rows show real broadcast positions (e.g. `Track 1, Foot 823,1011` — near-side winger at image bottom) with `Pitch (m)` = `—` because homography was off.

![T2 detections](https://app.devin.ai/attachments/6bc1d818-2be5-423d-b8bf-5ea939e6b6a3/pr4-football-t2-detections.png)

### <a id="t3"></a>T3 — Homography on, pitch mini-map populated

Stats strip now reads `projected 257 (100%)`. Mini-map panel `Foot-points on pitch (projected)` renders an SVG pitch (centre-line + centre-circle visible) with player-icon circles **scattered across both halves inside the 105×68 m rectangle**, matching the on-broadcast formation — not bunched at one corner and not all outside the pitch. Pitch(m) column now shows concrete decimals: `44.1, -2.4` · `17.7, 1.7` · `64.7, 19.4` · `88.0, 30.2` · `107.2, -0.3` · `28.5, 33.1` · `18.9, 25.1` · `60.9, 31.2` · `12.8, 17.0`.

![T3 pitch mini-map](https://app.devin.ai/attachments/2d63e362-ca78-4719-b64e-3e0df1061449/pr4-football-t3-minimap.png)

## Recording

Full continuous recording with annotations (T1 start/pass, T2 start/pass, T3 start/pass):
https://app.devin.ai/attachments/78f09112-4bcd-46b9-962a-ab4990ef9566/rec-a57b1193-8f9c-46f2-8d40-d8771fe1168d-edited.mp4

## Why this re-run was needed

Round 1 used `market-square.mp4` (4K pedestrian clip from `supervision.assets`)
to exercise the same code paths. That proved the UI/API wiring but not the
target domain, and the 4K/1920×1080 keypoint mismatch threw most foot-points
outside the pitch rectangle (still 100% projected, but visually all outside).

Round 2 uses a real DFL Bundesliga broadcast clip at the exact resolution the
default keypoints assume, so the inside-pitch geometry is visible and the
detector is exercised on the actual target distribution (long camera, players
scattered across the half, jersey contrast, motion blur, ad boards, etc.).

## Test input provenance

- File: `/home/ubuntu/cv-samples/0bfacc_0.mp4`
- Source: Roboflow `sports` repo, `examples/soccer/notebooks/football-players-detection.ipynb`, downloaded via gdown from a public Google Drive link (`gdown 12TqauVZ9tLAv8kWxTTBFWtgt2hNQ4_ZF`).
- Original dataset: DFL Bundesliga Data Shootout (Kaggle, CC-licensed).
- Properties: 19.9 MB, 1920×1080 @ 25 fps, 30 s, 750 frames.
- Direct `analyze_video(...)` sanity-check (max_frames=30, conf=0.25): 257 detections, 14 unique tracks. Matches the UI run exactly.
