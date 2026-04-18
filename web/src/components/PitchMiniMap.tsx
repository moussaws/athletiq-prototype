type Props = {
  points: { x: number; y: number; trackId: number; cls: number }[];
  pitchLength?: number;
  pitchWidth?: number;
};

const CLASS_COLOR: Record<number, string> = {
  0: "#4ade80", // person / player -> accent green
  1: "#fde68a", // sports ball     -> yellow
  2: "#60a5fa", // keeper / other  -> blue
};

// Renders foot-point pitch projections on a 105×68 m rectangle.
export default function PitchMiniMap({
  points,
  pitchLength = 105,
  pitchWidth = 68,
}: Props) {
  const svgWidth = 800;
  const svgHeight = svgWidth * (pitchWidth / pitchLength);
  const toSvg = (x: number, y: number): [number, number] => [
    (x / pitchLength) * svgWidth,
    (1 - y / pitchWidth) * svgHeight, // flip Y so 0 is bottom
  ];

  return (
    <svg
      viewBox={`0 0 ${svgWidth} ${svgHeight}`}
      className="w-full rounded bg-pitch"
    >
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
      {points.map((p, i) => {
        const [sx, sy] = toSvg(p.x, p.y);
        const color = CLASS_COLOR[p.cls] ?? "#a3a3a3";
        return (
          <g key={`${p.trackId}-${i}`}>
            <circle cx={sx} cy={sy} r={6} fill={color} fillOpacity={0.75} />
            <text
              x={sx}
              y={sy - 9}
              textAnchor="middle"
              fontSize={10}
              fill="white"
              fillOpacity={0.75}
            >
              {p.trackId}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
