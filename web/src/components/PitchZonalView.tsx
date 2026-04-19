import type { PitchZonalSummary, PitchZone } from "@/lib/api";

type Props = {
  zonal: PitchZonalSummary;
  pitchLength?: number;
  pitchWidth?: number;
};

/**
 * Diverging palette magenta (defender) <-> accent green (attacker), white at 0.5.
 *
 * Φ = 0.5 is the neutral line — neither side has a reliable advantage. Shifts
 * from 0.5 toward 1 fade into AthletIQ's accent green; shifts toward 0 fade
 * into the magenta accent. Both ramps stay dark enough to contrast against the
 * pitch background while keeping the white text legible.
 */
function colorForPhi(v: number): string {
  const clamped = Math.max(0, Math.min(1, v));
  if (clamped >= 0.5) {
    // 0.5 -> near-black neutral, 1.0 -> accent green (#10b981 ~ rgb(16,185,129))
    const t = (clamped - 0.5) * 2;
    const r = Math.round(22 + (16 - 22) * t);
    const g = Math.round(28 + (185 - 28) * t);
    const b = Math.round(36 + (129 - 36) * t);
    return `rgb(${r},${g},${b})`;
  }
  // 0.5 -> neutral, 0.0 -> magenta accent (#e11d74 ~ rgb(225,29,116))
  const t = (0.5 - clamped) * 2;
  const r = Math.round(22 + (225 - 22) * t);
  const g = Math.round(28 + (29 - 28) * t);
  const b = Math.round(36 + (116 - 36) * t);
  return `rgb(${r},${g},${b})`;
}

function SummaryCard({
  title,
  zone,
  phiLabel,
  accent,
}: {
  title: string;
  zone: PitchZone;
  phiLabel: string;
  accent: "accent" | "magenta" | "electric";
}) {
  const border =
    accent === "accent"
      ? "border-accent/40"
      : accent === "magenta"
      ? "border-magenta/40"
      : "border-electric/40";
  const bg =
    accent === "accent"
      ? "bg-accent/5"
      : accent === "magenta"
      ? "bg-magenta/5"
      : "bg-electric/5";
  return (
    <div className={`rounded border ${border} ${bg} p-3`}>
      <div className="text-[10px] uppercase tracking-wider text-white/50">
        {title}
      </div>
      <div className="mt-1 text-sm font-medium text-white">{zone.label}</div>
      <div className="mt-1 text-xs text-white/70">
        {phiLabel}: <span className="text-white">{zone.phi_mean.toFixed(2)}</span>
      </div>
      <div className="mt-1 text-[10px] text-white/40">
        ≈ x {zone.x_range[0].toFixed(0)}–{zone.x_range[1].toFixed(0)} m · y{" "}
        {zone.y_range[0].toFixed(0)}–{zone.y_range[1].toFixed(0)} m
      </div>
    </div>
  );
}

export default function PitchZonalView({
  zonal,
  pitchLength = 105,
  pitchWidth = 68,
}: Props) {
  const { zones, channels, thirds, balance_attacker_pct } = zonal;
  const svgWidth = 800;
  const svgHeight = svgWidth * (pitchWidth / pitchLength);

  // Re-bucket zones for rendering: rows = channels (top=first channel), cols = thirds.
  const nCols = thirds.length;
  const nRows = channels.length;
  const byIndex: (PitchZone | undefined)[][] = Array.from(
    { length: nRows },
    () => new Array<PitchZone | undefined>(nCols).fill(undefined),
  );
  for (const z of zones) {
    byIndex[z.channel_index][z.third_index] = z;
  }

  return (
    <div className="space-y-4">
      {/* Coach headline */}
      <div className="rounded border border-accent/30 bg-accent/5 p-3 text-sm text-white/90">
        {zonal.headline}
      </div>

      {/* Four summary cards */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <SummaryCard
          title="Most dangerous attacking zone"
          zone={zonal.hottest_attack}
          phiLabel="Φ"
          accent="accent"
        />
        <SummaryCard
          title="Defence's strongest patch (attacker's weakest)"
          zone={zonal.defensive_weak_point}
          phiLabel="Φ"
          accent="magenta"
        />
        <SummaryCard
          title="Safest build-up zone"
          zone={zonal.opportunity_zone}
          phiLabel="Φ"
          accent="electric"
        />
        <div className="rounded border border-white/15 bg-white/5 p-3">
          <div className="text-[10px] uppercase tracking-wider text-white/50">
            Territorial balance
          </div>
          <div className="mt-2 flex h-2 overflow-hidden rounded-full bg-white/10">
            <div
              className="h-full bg-accent"
              style={{ width: `${balance_attacker_pct.toFixed(1)}%` }}
            />
            <div
              className="h-full bg-magenta"
              style={{ width: `${(100 - balance_attacker_pct).toFixed(1)}%` }}
            />
          </div>
          <div className="mt-2 flex justify-between text-xs text-white/70">
            <span>
              Attacker{" "}
              <span className="text-white">
                {balance_attacker_pct.toFixed(0)}%
              </span>
            </span>
            <span>
              Defender{" "}
              <span className="text-white">
                {(100 - balance_attacker_pct).toFixed(0)}%
              </span>
            </span>
          </div>
        </div>
      </div>

      {/* 4x3 zonal tiles on a pitch */}
      <div className="rounded border border-white/10 bg-pitch p-3">
        <svg
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          className="w-full"
          aria-label="Zonal pitch-control read"
        >
          {byIndex.map((row, ri) =>
            row.map((z, ci) => {
              if (!z) return null;
              const x0 = (z.x_range[0] / pitchLength) * svgWidth;
              const x1 = (z.x_range[1] / pitchLength) * svgWidth;
              const y0 = (z.y_range[0] / pitchWidth) * svgHeight;
              const y1 = (z.y_range[1] / pitchWidth) * svgHeight;
              const w = x1 - x0;
              const h = y1 - y0;
              return (
                <g key={`${ri}-${ci}`}>
                  <rect
                    x={x0}
                    y={y0}
                    width={w}
                    height={h}
                    fill={colorForPhi(z.phi_mean)}
                    opacity={0.92}
                  />
                  <text
                    x={x0 + w / 2}
                    y={y0 + h / 2 - 6}
                    textAnchor="middle"
                    fontSize={14}
                    fill="white"
                    fontWeight={600}
                    opacity={0.95}
                  >
                    {z.phi_mean.toFixed(2)}
                  </text>
                  <text
                    x={x0 + w / 2}
                    y={y0 + h / 2 + 14}
                    textAnchor="middle"
                    fontSize={10}
                    fill="white"
                    opacity={0.6}
                  >
                    {z.channel}
                  </text>
                  <text
                    x={x0 + w / 2}
                    y={y0 + h / 2 + 28}
                    textAnchor="middle"
                    fontSize={9}
                    fill="white"
                    opacity={0.45}
                  >
                    {z.third}
                  </text>
                </g>
              );
            }),
          )}
          {/* pitch markings */}
          <rect
            x={1}
            y={1}
            width={svgWidth - 2}
            height={svgHeight - 2}
            fill="none"
            stroke="white"
            strokeOpacity={0.55}
            strokeWidth={2}
          />
          <line
            x1={svgWidth / 2}
            y1={0}
            x2={svgWidth / 2}
            y2={svgHeight}
            stroke="white"
            strokeOpacity={0.45}
            strokeWidth={1.5}
          />
          <circle
            cx={svgWidth / 2}
            cy={svgHeight / 2}
            r={svgHeight * 0.12}
            fill="none"
            stroke="white"
            strokeOpacity={0.45}
            strokeWidth={1.5}
          />
          {/* attacking direction arrow */}
          <g opacity={0.55}>
            <line
              x1={svgWidth - 120}
              y1={svgHeight - 14}
              x2={svgWidth - 20}
              y2={svgHeight - 14}
              stroke="white"
              strokeWidth={1.5}
            />
            <polygon
              points={`${svgWidth - 20},${svgHeight - 14} ${svgWidth - 30},${
                svgHeight - 9
              } ${svgWidth - 30},${svgHeight - 19}`}
              fill="white"
            />
            <text
              x={svgWidth - 125}
              y={svgHeight - 18}
              textAnchor="end"
              fontSize={10}
              fill="white"
            >
              attacking →
            </text>
          </g>
        </svg>
      </div>

      {/* Palette legend */}
      <div className="flex items-center gap-3 text-xs text-white/60">
        <span>Defender controls</span>
        <span className="inline-block h-2 w-40 rounded-full bg-gradient-to-r from-magenta via-white/20 to-accent" />
        <span>Attacker controls</span>
      </div>
    </div>
  );
}
