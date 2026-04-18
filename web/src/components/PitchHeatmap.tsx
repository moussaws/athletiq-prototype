type Props = {
  phi: number[][];
  x: number[];
  y: number[];
  pitchLength?: number;
  pitchWidth?: number;
};

export default function PitchHeatmap({
  phi,
  x,
  y,
  pitchLength = 105,
  pitchWidth = 68,
}: Props) {
  const rows = phi.length;
  const cols = rows > 0 ? phi[0].length : 0;
  if (rows === 0 || cols === 0) return null;

  const svgWidth = 800;
  const svgHeight = svgWidth * (pitchWidth / pitchLength);

  const cellW = svgWidth / cols;
  const cellH = svgHeight / rows;

  const colorFor = (v: number): string => {
    // 0 -> dark green (defender), 1 -> bright accent (attacker), mid -> gray
    const clamped = Math.max(0, Math.min(1, v));
    const r = Math.round(74 * clamped + 15 * (1 - clamped));
    const g = Math.round(222 * clamped + 43 * (1 - clamped));
    const b = Math.round(128 * clamped + 29 * (1 - clamped));
    return `rgb(${r},${g},${b})`;
  };

  return (
    <svg
      viewBox={`0 0 ${svgWidth} ${svgHeight}`}
      className="w-full rounded bg-pitch"
    >
      {phi.map((row, ri) =>
        row.map((v, ci) => (
          <rect
            key={`${ri}-${ci}`}
            x={ci * cellW}
            y={ri * cellH}
            width={cellW + 0.5}
            height={cellH + 0.5}
            fill={colorFor(v)}
            opacity={0.85}
          />
        )),
      )}
      {/* pitch markings */}
      <rect
        x={1}
        y={1}
        width={svgWidth - 2}
        height={svgHeight - 2}
        fill="none"
        stroke="white"
        strokeOpacity={0.5}
        strokeWidth={2}
      />
      <line
        x1={svgWidth / 2}
        y1={0}
        x2={svgWidth / 2}
        y2={svgHeight}
        stroke="white"
        strokeOpacity={0.4}
        strokeWidth={1.5}
      />
      <circle
        cx={svgWidth / 2}
        cy={svgHeight / 2}
        r={svgHeight * 0.12}
        fill="none"
        stroke="white"
        strokeOpacity={0.4}
        strokeWidth={1.5}
      />
    </svg>
  );
}
