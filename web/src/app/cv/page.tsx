"use client";

import { useEffect, useMemo, useState } from "react";
import PitchMiniMap from "@/components/PitchMiniMap";
import type {
  CVAnalysisResponse,
  CVCapabilities,
  CVDetection,
} from "@/lib/api";

const API_BASE = "/backend";
const MAX_DETECTIONS_SHOWN = 50;

// A 4-corner calibration for a 105×68 m broadcast frame: top-left, top-right,
// bottom-right, bottom-left corners of the pitch. Users can paste their own
// keypoints or edit image_pts to match their footage.
const DEFAULT_KEYPOINTS = JSON.stringify(
  {
    image_pts: [
      [100, 100],
      [1820, 100],
      [1820, 980],
      [100, 980],
    ],
    pitch_pts: [
      [0, 68],
      [105, 68],
      [105, 0],
      [0, 0],
    ],
  },
  null,
  2,
);

export default function CVPage() {
  const [caps, setCaps] = useState<CVCapabilities | null>(null);
  const [capsError, setCapsError] = useState<string | null>(null);

  const [file, setFile] = useState<File | null>(null);
  const [useHomography, setUseHomography] = useState(false);
  const [keypointsJson, setKeypointsJson] = useState(DEFAULT_KEYPOINTS);
  const [maxFrames, setMaxFrames] = useState(30);
  const [conf, setConf] = useState(0.25);

  const [busy, setBusy] = useState(false);
  const [analysis, setAnalysis] = useState<CVAnalysisResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/cv/capabilities`, { cache: "no-store" })
      .then(async (r) => {
        if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
        return (await r.json()) as CVCapabilities;
      })
      .then(setCaps)
      .catch((e) =>
        setCapsError(e instanceof Error ? e.message : String(e)),
      );
  }, []);

  const tracks = useMemo(() => {
    if (!analysis) return new Map<number, CVDetection[]>();
    const m = new Map<number, CVDetection[]>();
    for (const d of analysis.detections) {
      const arr = m.get(d.track_id) ?? [];
      arr.push(d);
      m.set(d.track_id, arr);
    }
    return m;
  }, [analysis]);

  const pitchPoints = useMemo(() => {
    if (!analysis) return [];
    return analysis.detections
      .filter((d) => d.pitch_xy != null)
      .map((d) => ({
        x: (d.pitch_xy as number[])[0],
        y: (d.pitch_xy as number[])[1],
        trackId: d.track_id,
        cls: d.cls,
      }));
  }, [analysis]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) {
      setError("Select an MP4 to analyze.");
      return;
    }
    setBusy(true);
    setError(null);
    setAnalysis(null);
    try {
      if (useHomography) {
        JSON.parse(keypointsJson);
      }
      const form = new FormData();
      form.append("video", file);
      form.append("max_frames", String(maxFrames));
      form.append("conf", String(conf));
      if (useHomography) form.append("keypoints_json", keypointsJson);

      const r = await fetch(`${API_BASE}/api/cv/analyze`, {
        method: "POST",
        body: form,
      });
      if (!r.ok) {
        const text = await r.text().catch(() => r.statusText);
        throw new Error(`${r.status}: ${text}`);
      }
      const data = (await r.json()) as CVAnalysisResponse;
      setAnalysis(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  const capsBanner = (() => {
    if (capsError) {
      return (
        <div className="rounded border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-200">
          Could not reach the backend API: {capsError}
          <div className="mt-1 text-white/40">
            Start it with <code>make api</code>.
          </div>
        </div>
      );
    }
    if (!caps) {
      return (
        <div className="rounded border border-white/10 bg-white/5 p-4 text-sm text-white/50">
          Checking CV backend capabilities…
        </div>
      );
    }
    if (!caps.cv_available) {
      return (
        <div className="rounded border border-amber-400/40 bg-amber-400/10 p-4 text-sm text-amber-100">
          <div className="font-medium">CV extras not installed on the server.</div>
          <div className="mt-1 text-amber-100/80">
            Install with{" "}
            <code className="rounded bg-black/30 px-1">
              pip install -e &apos;.[cv]&apos;
            </code>{" "}
            to enable YOLOv10 + ByteTrack analysis. Reason:{" "}
            <span className="text-amber-100/60">{caps.reason ?? "unknown"}</span>
          </div>
        </div>
      );
    }
    return (
      <div className="rounded border border-emerald-400/40 bg-emerald-400/10 p-4 text-sm text-emerald-100">
        CV pipeline ready — YOLOv10 + ByteTrack (+ optional Huber-refined
        homography) available on the server.
      </div>
    );
  })();

  const disableSubmit = busy || !file || caps?.cv_available === false;

  return (
    <div className="max-w-5xl">
      <h1 className="text-3xl font-semibold">Tape view — from footage to pitch</h1>
      <p className="mt-2 text-white/60">
        Drop in a short broadcast clip. We detect every player, track them
        across frames, and (if you hand us four corners of the pitch) project
        them onto a real 105×68 m pitch so you can see where your side
        actually lived on the field — compactness, shape, horizontal spread.
        Runs with a single camera, no tracking hardware required.
      </p>

      <div className="mt-6">{capsBanner}</div>

      <form
        onSubmit={handleSubmit}
        className="mt-6 rounded border border-white/10 bg-white/5 p-5 text-sm"
      >
        <label className="block">
          <span className="text-white/70">MP4 file</span>
          <input
            type="file"
            accept="video/mp4,video/x-m4v,video/*"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="mt-1 block w-full text-white/80 file:mr-3 file:rounded file:border-0 file:bg-accent/20 file:px-3 file:py-1.5 file:text-accent hover:file:bg-accent/30"
          />
        </label>

        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <label className="block">
            <span className="text-white/70">Max frames</span>
            <input
              type="number"
              min={1}
              max={300}
              value={maxFrames}
              onChange={(e) => setMaxFrames(Number(e.target.value))}
              className="mt-1 block w-full rounded border border-white/10 bg-rail px-3 py-1.5 text-white"
            />
          </label>
          <label className="block">
            <span className="text-white/70">Detection confidence</span>
            <input
              type="number"
              min={0}
              max={1}
              step={0.05}
              value={conf}
              onChange={(e) => setConf(Number(e.target.value))}
              className="mt-1 block w-full rounded border border-white/10 bg-rail px-3 py-1.5 text-white"
            />
          </label>
        </div>

        <div className="mt-4">
          <label className="inline-flex items-center gap-2 text-white/70">
            <input
              type="checkbox"
              checked={useHomography}
              onChange={(e) => setUseHomography(e.target.checked)}
            />
            Project foot-points to pitch coordinates (needs keypoints)
          </label>
          {useHomography && (
            <textarea
              value={keypointsJson}
              onChange={(e) => setKeypointsJson(e.target.value)}
              rows={10}
              spellCheck={false}
              className="mt-2 block w-full rounded border border-white/10 bg-black/30 px-3 py-2 font-mono text-xs text-white/80"
            />
          )}
        </div>

        <div className="mt-4 flex items-center gap-3">
          <button
            type="submit"
            disabled={disableSubmit}
            className="rounded bg-accent/20 px-4 py-1.5 text-accent hover:bg-accent/30 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy ? "analyzing…" : "analyze"}
          </button>
          {file && (
            <span className="text-xs text-white/50">
              {file.name} · {(file.size / (1024 * 1024)).toFixed(1)} MB
            </span>
          )}
        </div>
      </form>

      {error && (
        <div className="mt-6 rounded border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-200">
          {error}
        </div>
      )}

      {analysis && (
        <div className="mt-6 space-y-6">
          <TapeReadout
            analysis={analysis}
            tracks={tracks.size}
            pitchPoints={pitchPoints}
          />
          <details className="rounded border border-white/10 bg-white/[0.02] p-5 text-sm">
            <summary className="cursor-pointer select-none font-medium text-white/80">
              Analyst view · raw detection stats
            </summary>
            <div className="mt-4 flex flex-wrap gap-6">
              <Stat label="fps" value={analysis.fps.toFixed(1)} />
              <Stat
                label="resolution"
                value={`${analysis.width}×${analysis.height}`}
              />
              <Stat label="detections" value={analysis.n_detections} />
              <Stat label="unique tracks" value={tracks.size} />
              <Stat
                label="projected"
                value={`${pitchPoints.length}${
                  analysis.n_detections > 0
                    ? ` (${Math.round(
                        (pitchPoints.length / analysis.n_detections) * 100,
                      )}%)`
                    : ""
                }`}
              />
            </div>
          </details>

          {pitchPoints.length > 0 && (
            <div className="rounded border border-white/10 bg-white/5 p-4">
              <div className="flex items-center justify-between text-sm">
                <div className="font-medium">Foot-points on pitch (projected)</div>
                <div className="text-xs text-white/50">
                  {pitchPoints.length} points · 105×68 m
                </div>
              </div>
              <div className="mt-4">
                <PitchMiniMap points={pitchPoints} />
              </div>
            </div>
          )}

          <div className="overflow-hidden rounded border border-white/10">
            <table className="w-full text-sm">
              <thead className="bg-white/5 text-left text-white/60">
                <tr>
                  <th className="px-3 py-2 text-right">Frame</th>
                  <th className="px-3 py-2 text-right">Track</th>
                  <th className="px-3 py-2 text-right">Cls</th>
                  <th className="px-3 py-2 text-right">Conf</th>
                  <th className="px-3 py-2 text-right">Foot (px)</th>
                  <th className="px-3 py-2 text-right">Pitch (m)</th>
                </tr>
              </thead>
              <tbody>
                {analysis.detections.slice(0, MAX_DETECTIONS_SHOWN).map((d, i) => (
                  <tr
                    key={`${d.frame}-${d.track_id}-${i}`}
                    className="border-t border-white/5"
                  >
                    <td className="px-3 py-1.5 text-right tabular-nums">
                      {d.frame}
                    </td>
                    <td className="px-3 py-1.5 text-right tabular-nums">
                      {d.track_id}
                    </td>
                    <td className="px-3 py-1.5 text-right text-white/60">
                      {d.cls}
                    </td>
                    <td className="px-3 py-1.5 text-right tabular-nums">
                      {d.conf.toFixed(2)}
                    </td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-white/70">
                      {(d.foot_xy as number[])[0].toFixed(0)},{" "}
                      {(d.foot_xy as number[])[1].toFixed(0)}
                    </td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-white/70">
                      {d.pitch_xy
                        ? `${(d.pitch_xy as number[])[0].toFixed(1)}, ${(
                            d.pitch_xy as number[]
                          )[1].toFixed(1)}`
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="border-t border-white/5 bg-white/5 px-3 py-2 text-xs text-white/50">
              showing{" "}
              {Math.min(analysis.detections.length, MAX_DETECTIONS_SHOWN)} of{" "}
              {analysis.detections.length} detections
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-white/40">
        {label}
      </div>
      <div className="mt-0.5 text-lg font-medium tabular-nums">{value}</div>
    </div>
  );
}

type PitchPoint = { x: number; y: number; trackId: number; cls: number };

function TapeReadout({
  analysis,
  tracks,
  pitchPoints,
}: {
  analysis: CVAnalysisResponse;
  tracks: number;
  pitchPoints: PitchPoint[];
}) {
  const frames = Math.max(1, analysis.n_detections > 0
    ? Math.max(...analysis.detections.map((d) => d.frame)) + 1
    : 1);
  const avgOnScreen = analysis.n_detections / frames;
  // Compactness: 105×68 m pitch is ~7140 m² of area; an actively playing
  // team tends to occupy ~30–60 m of that at a time. We compute it from
  // the spread of foot-points that actually landed inside the pitch.
  const inside = pitchPoints.filter(
    (p) => p.x >= 0 && p.x <= 105 && p.y >= 0 && p.y <= 68,
  );
  const hasProjection = pitchPoints.length > 0;
  let horizSpread = 0;
  let vertSpread = 0;
  let insidePct = 0;
  if (inside.length > 1) {
    const xs = inside.map((p) => p.x);
    const ys = inside.map((p) => p.y);
    horizSpread = Math.max(...xs) - Math.min(...xs);
    vertSpread = Math.max(...ys) - Math.min(...ys);
    insidePct = Math.round((inside.length / pitchPoints.length) * 100);
  }

  const lines: string[] = [];
  lines.push(
    `Tracked ${tracks} distinct figure${tracks === 1 ? "" : "s"} across ${frames} frame${frames === 1 ? "" : "s"} — on average ${avgOnScreen.toFixed(1)} on screen.`,
  );
  if (hasProjection && inside.length > 1) {
    const depthVerdict =
      vertSpread < 30
        ? "a very compact block defensively"
        : vertSpread < 50
          ? "a balanced vertical shape"
          : "a stretched shape with defenders and attackers far apart";
    const widthVerdict =
      horizSpread < 30
        ? "narrow horizontally — touchlines under-used"
        : horizSpread < 55
          ? "reasonable horizontal spread"
          : "full width of the pitch used";
    lines.push(
      `On the pitch the side showed ${depthVerdict} (≈${vertSpread.toFixed(0)} m deep) and ${widthVerdict} (≈${horizSpread.toFixed(0)} m wide).`,
    );
    if (insidePct < 60) {
      lines.push(
        `Heads-up: only ${insidePct}% of foot-points landed inside the 105×68 m pitch — your keypoint calibration may be off, so read the compactness numbers as indicative only.`,
      );
    }
  } else if (!hasProjection) {
    lines.push(
      "Tick the pitch-projection option and supply four corner keypoints to turn these detections into a bird's-eye pitch readout (compactness, width, depth).",
    );
  }

  return (
    <div className="rounded border border-emerald-500/30 bg-emerald-500/10 p-5 text-sm text-emerald-100">
      <div className="font-medium">Coach readout</div>
      <div className="mt-2 space-y-2">
        {lines.map((l, i) => (
          <p key={i}>{l}</p>
        ))}
      </div>
      {hasProjection && inside.length > 1 && (
        <div className="mt-4 grid grid-cols-3 gap-2">
          <ReadoutStat label="On screen" value={avgOnScreen.toFixed(1)} />
          <ReadoutStat
            label="Shape depth"
            value={`${vertSpread.toFixed(0)} m`}
          />
          <ReadoutStat
            label="Shape width"
            value={`${horizSpread.toFixed(0)} m`}
          />
        </div>
      )}
    </div>
  );
}

function ReadoutStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded bg-black/30 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wide text-emerald-200/60">
        {label}
      </div>
      <div className="mt-0.5 text-base font-medium tabular-nums text-emerald-50">
        {value}
      </div>
    </div>
  );
}
