# PR #4 Test Plan — `/cv` upload page (Pillar C)

Primary end-to-end flow: upload a **real football broadcast MP4** to `/cv`, run
YOLOv10 + ByteTrack on the server, tick the homography box so foot-points
project to pitch coordinates, and verify the rendered results contain values
that could only exist if both the multipart POST path *and* the homography
projection actually ran — against footage the whole product is designed for.

Single continuous recording. 3 adversarial assertions. This is the second
test round for PR #4 — the first used a pedestrian clip to exercise the same
code paths; this round re-runs T1+T2+T3 on actual broadcast football to
address the user's valid concern that pedestrian footage doesn't prove the
pipeline works on the target domain.

## Pre-flight (already verified, not part of recording)
- Backend up on :8000: `GET /api/cv/capabilities → {"cv_available":true,"reason":null}` ✔
- Dashboard up on :3000: `GET /cv → 200` ✔
- Sample clip: `/home/ubuntu/cv-samples/0bfacc_0.mp4` (19.9 MB, 1920×1080, 25 fps, 30 s — DFL Bundesliga Data Shootout broadcast clip from Roboflow `sports/examples/soccer/setup.sh`, originally a Kaggle CC-licensed dataset). Direct `analyze_video` sanity-check: **257 detections, 14 unique tracks** across 30 frames at conf=0.25. Real broadcast football: long camera, players scattered across the half, ball visible, jersey contrast, motion blur.
- Clip resolution (1920×1080) matches the `/cv` form's default keypoint rectangle (100,100)-(1820,980), so T3 should land most foot-points **inside** the 105×68 m pitch rectangle — unlike the first round with a 4K pedestrian clip where the keypoint mismatch threw most points off-pitch.

## T1 — Capability banner reflects the live backend (emerald, not amber)

Code under test: `web/src/app/cv/page.tsx:119-162`.

- Navigate: Home → click "Pillar C — CV pipeline" card → land on `/cv`.
- **PASS**: An emerald (green) banner renders with text starting `CV pipeline ready — YOLOv10 + ByteTrack`.
- **FAIL**: Amber "CV extras not installed" banner, red backend-unreachable banner, or blank.
- Why this distinguishes broken-vs-working: the banner's branch comes from `caps.cv_available`. If the capabilities fetch or the Next.js `/backend/*` rewrite were misconfigured, the banner would either be amber (boolean false) or red (fetch error) — it would not read "ready".

## T2 — Real football MP4 upload returns a populated detections table

Code under test: `web/src/app/cv/page.tsx:86-113` (multipart POST) and `:250-321` (results render).

- On `/cv`, click the file input, select `/home/ubuntu/cv-samples/0bfacc_0.mp4`.
- Leave max_frames = **30**, conf = **0.25**, homography checkbox **unchecked** first.
- Click **analyze**.
- Wait until button text returns from "analyzing…" back to "analyze".
- **PASS (all four must hold)**:
  1. No red error banner appears.
  2. The "detections" stat is a positive integer **≥ 100** (direct pipeline sanity-check produced 257; threshold well above any plausible zero / off-by-one / single-frame failure).
  3. The "unique tracks" stat is **≥ 5** (ByteTrack assigns stable IDs across frames; sanity-check produced 14 — with ~20 players on-screen in broadcast football this should never be under 5 if tracking runs at all).
  4. The detections table body renders at least one row where the `Frame` column is a concrete number, the `Track` column is ≥ 1, the `Conf` column is between 0.25 and 1.00, and the `Pitch (m)` column shows `—` (since homography was disabled).
- **FAIL**: any red banner, `detections: 0`, `unique tracks: 0`, empty `<tbody>`, or a `Pitch (m)` value other than `—` when the checkbox was unchecked.
- Why this distinguishes broken-vs-working: a broken multipart path would 5xx with a red banner; a broken tracker hookup would leave `unique_tracks = 0`; a broken "no-homography" branch would either crash on null `pitch_xy` (TypeError from `.toFixed`) or leak a non-dash value into the Pitch column. Using a real broadcast football clip also stresses the detector on the target domain — small, scattered players in motion — rather than easy, upright, close-up pedestrians.

## T3 — Homography checkbox produces a non-empty pitch mini-map with most points inside the pitch

Code under test: `web/src/app/cv/page.tsx:73-84, 97-100, 282-296` and `web/src/components/PitchMiniMap.tsx`.

- Still on `/cv`, tick the **"Project foot-points to pitch coordinates"** checkbox.
- Leave the default keypoints JSON as-is (4 corners of a 1920×1080 → 105×68 m rectangle, matching the clip resolution).
- Click **analyze** again.
- **PASS (all three must hold)**:
  1. The "projected" stat shows a positive integer matching the pattern `N (P%)` where `N > 0` and `P = 100%` (every detection gets a `pitch_xy` since homography always succeeds on a valid 4-point correspondence).
  2. A new panel titled **"Foot-points on pitch (projected)"** appears with an inline SVG. The SVG contains **at least 5 `<circle>` elements** distributed across the 105×68 rectangle (centre-line and centre-circle visible, multiple accent-green dots clustered inside the pitch rather than all bunched at a corner).
  3. The detections table's `Pitch (m)` column now shows concrete decimals in format `X.X, Y.Y` where for most visible rows `0 ≤ X ≤ 105` and `0 ≤ Y ≤ 68`. Unlike the pedestrian round, this is actual football on a pitch with a keypoint box that matches the clip resolution, so inside-pitch coordinates are the expected outcome.
- **FAIL**: "projected" stays at 0, mini-map panel missing, SVG has no circles, SVG has circles but they're all outside the 105×68 pitch rectangle (would indicate the homography math ran but the keypoints wiring is wrong), or `Pitch (m)` column still shows `—`.
- Why this distinguishes broken-vs-working: T3 only passes if (a) the checkbox actually rebinds the request payload with `use_homography=true` + keypoints, (b) the backend computes the Huber-robust homography and returns `pitch_xy`, and (c) the mini-map component actually renders those points. Unlike the first (pedestrian) test round, the tighter "inside-pitch" geometry check also catches the case where homography runs but keypoints are silently swapped/dropped, which would scatter points far outside the 105×68 box.
