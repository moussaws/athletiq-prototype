# PR #4 — `/cv` page end-to-end test report

Tested the merged `/cv` page (PR #4) end-to-end against a live FastAPI backend with CV extras installed (`torch` 2.11.0 CPU + `ultralytics` 8.4.38 + `supervision` 0.27.0.post2, YOLOv10n weights auto-downloaded to `~/.cache/`).

## Summary

| # | Test | Result |
|---|------|--------|
| T1 | It should show an emerald capability banner when CV extras are installed | **passed** |
| T2 | It should upload an MP4 and return a populated detections table | **passed** |
| T3 | It should project foot-points to pitch coordinates when homography is enabled | **passed** |

Full flow ran on one continuous recording; all three adversarial assertions held.

## Escalations

- **Input-selection friction (not a PR bug).** My first sample clip (a 5 s basketball YouTube-short recoded to MP4) produced **0 detections** from YOLOv10n at `conf=0.25, max_frames=30`. That is not a code bug in PR #4 — running `athletiq.cv.pipeline.analyze_video` directly on the same file returned the same empty result. Swapped to `supervision.assets.VideoAssets.MARKET_SQUARE` (pedestrian-dense 4K clip) which produces 105 detections / 7 tracks on the identical parameters. Worth noting for anyone reproducing: YOLOv10n's COCO person class needs a scene where people occupy a reasonable portion of the frame at near-upright orientation. The adjusted plan is in [`test-plan-pr4.md`](./test-plan-pr4.md).
- **Projected-outside-pitch behaviour.** The default keypoint JSON maps a 1920×1080 rectangle to a 105×68 m pitch. The test clip is 3840×2160, so most foot-points project to Y coordinates like `-215 m` (far below the pitch). The pipeline still returns them in `pitch_xy` and the frontend counts them in `projected: 105 (100%)` — it counts "homography ran", not "projected inside pitch". The mini-map SVG renders all circles at their computed SVG coordinates without clipping, so outside-pitch circles fall outside the viewBox and aren't visible. One inside-pitch circle is visible (track 4 at `(24, 1)` → near bottom-left corner). If you want "projected" to mean "inside pitch", that's a small follow-up in `page.tsx:261-269` — not a regression in PR #4.
- Not a blocker, but the capability banner text renders `CV pipeline ready — YOLOv10 + ByteTrack (+ optional Huber-refined homography) available on the server.` (actual) vs plan wording `CV pipeline ready — YOLOv10 + ByteTrack` — match is on the prefix, passed.

## T1 — Capability banner reflects the live backend

Navigated Home → sidebar "CV pipeline" → `/cv`. An **emerald** banner renders reading *"CV pipeline ready — YOLOv10 + ByteTrack (+ optional Huber-refined homography) available on the server."* No amber "extras not installed" state, no red "backend unreachable" state. The Next.js `/backend/*` rewrite reached FastAPI's `/api/cv/capabilities` endpoint and the frontend branched into the `caps.cv_available === true` arm.

![T1 — emerald capability banner on /cv](https://app.devin.ai/attachments/1a33644f-b0eb-4f06-8fbd-e0a280dd69ae/t1-capability-banner.png)

## T2 — Real MP4 upload returns a populated detections table

Selected `/home/ubuntu/cv-samples/market-square.mp4` (20.3 MB, 4K, 60 FPS) via the file input. Kept `max_frames=30`, `conf=0.25`, homography **unchecked**. Clicked **analyze**. Button went to "analyzing…" and returned ~38 s later.

Observed stats: `fps 60.0 · resolution 2160×3840 · detections 105 · unique tracks 7 · projected 0`.

Table renders with concrete rows — e.g. `frame=0 track=1 cls=0 conf=0.50 foot=(1426,3775) pitch=—`, `frame=3 track=3 cls=0 conf=0.33 foot=(1121,1628) pitch=—`. Footer: *"showing 50 of 105 detections"* (the 50-row UI cap).

All four PASS criteria held:
- no red error banner,
- detections = **105** (≥ 50 threshold),
- unique tracks = **7** (≥ 3 threshold),
- every rendered row's `Pitch (m)` column = `—` (homography was off).

![T2 — 105 detections / 7 tracks / Pitch column = —](https://app.devin.ai/attachments/6f948a6a-1bad-438a-b666-29ad9b7af48b/t2-detections-table.png)

## T3 — Homography checkbox produces a populated pitch projection

Ticked **"Project foot-points to pitch coordinates"**, kept the default 4-corner keypoints JSON as-is, re-clicked **analyze**.

Observed stats: `detections 105 · unique tracks 7 · projected 105 (100%)`. A new *"Foot-points on pitch (projected)"* panel rendered below, labelled *"105 points · 105×68 m"*, containing an inline SVG pitch rectangle with centre-line and centre-circle drawn.

All three PASS criteria held:
- `projected` = **105 (100%)** — a positive integer ≥ 1;
- the mini-map panel renders with a non-empty SVG; one inside-pitch track-4 circle is visible at the bottom-left of the rectangle (corresponding to rows like `frame=14 track=4 foot=(494,966) pitch=(24.0, 1.0)` in the table);
- table `Pitch (m)` column now contains concrete decimals — e.g. `(81.0, -216.0)`, `(62.3, -50.1)`, `(24.0, 1.0)`, `(97.2, -206.4)` — across at least 50 of 105 rows, not `—`.

![T3 — projected 105 (100%), mini-map with inside-pitch green circle visible (track 4)](https://app.devin.ai/attachments/112bb259-09c6-4f68-b4c0-76e897cf67fc/t3-pitch-minimap.png)

## Recording

Full continuous recording of T1 → T2 → T3 with `test_start` / `assertion` annotations:
https://app.devin.ai/attachments/997c0cf5-f696-4f6f-b6a9-44f53cc85d26/rec-52da7df8-d0c2-4e98-b3e3-44d16e55d7ce-edited.mp4

## Setup used

- Backend: `uv run uvicorn athletiq.api.main:app --host 127.0.0.1 --port 8000` (with `[cv]` extras)
- Dashboard: `cd web && npm run dev` on :3000, proxying `/backend/*` → `127.0.0.1:8000/*`
- Weights: `yolov10n.pt` auto-downloaded to `~/.cache/yolov10/` on first call (~5.6 MB)
- Clip: `supervision.assets.VideoAssets.MARKET_SQUARE` → `/home/ubuntu/cv-samples/market-square.mp4`

## Devin session

https://app.devin.ai/sessions/e9df82d696244f1698b684f56e63506f
