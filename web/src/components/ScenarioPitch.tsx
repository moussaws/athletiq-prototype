"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import type { Point } from "@/lib/api";

/**
 * Draggable-dot pitch with a Φ heatmap underlay.
 *
 * Coordinates are in metres on a 105 × 68 pitch. Attackers are rendered as
 * cyan dots, defenders as magenta. Both teams can be dragged with the mouse;
 * keyboard fallback (arrow keys when a dot is focused) nudges the selected
 * dot by 1 metre. Drag-end fires ``onChange`` with the complete new state so
 * the parent can debounce a Φ recompute.
 *
 * The Φ underlay is optional — if ``phi`` is null/empty the heatmap slot is
 * transparent and the pitch shows only markings + dots.
 */

const PITCH_LENGTH = 105;
const PITCH_WIDTH = 68;
const SVG_WIDTH = 800;
const SVG_HEIGHT = SVG_WIDTH * (PITCH_WIDTH / PITCH_LENGTH);
const DOT_R = 10;

type Team = "attacker" | "defender" | "ball";
type DragTarget = { team: Team; index: number } | null;

type Props = {
  attackers: Point[];
  defenders: Point[];
  ball: Point;
  phi?: number[][] | null;
  onChange: (next: {
    attackers: Point[];
    defenders: Point[];
    ball: Point;
    changed: Team;
  }) => void;
  disabled?: boolean;
};

function colorForPhi(v: number): string {
  const c = Math.max(0, Math.min(1, v));
  const r = Math.round(74 * c + 15 * (1 - c));
  const g = Math.round(222 * c + 43 * (1 - c));
  const b = Math.round(128 * c + 29 * (1 - c));
  return `rgb(${r},${g},${b})`;
}

function metresToSvg(p: Point): { cx: number; cy: number } {
  return {
    cx: (p.x / PITCH_LENGTH) * SVG_WIDTH,
    cy: (p.y / PITCH_WIDTH) * SVG_HEIGHT,
  };
}

function svgToMetres(
  evt: { clientX: number; clientY: number },
  svg: SVGSVGElement,
): Point {
  const rect = svg.getBoundingClientRect();
  const px = evt.clientX - rect.left;
  const py = evt.clientY - rect.top;
  const x = (px / rect.width) * PITCH_LENGTH;
  const y = (py / rect.height) * PITCH_WIDTH;
  return {
    x: Math.max(0, Math.min(PITCH_LENGTH, x)),
    y: Math.max(0, Math.min(PITCH_WIDTH, y)),
  };
}

export default function ScenarioPitch({
  attackers,
  defenders,
  ball,
  phi,
  onChange,
  disabled = false,
}: Props) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [drag, setDrag] = useState<DragTarget>(null);
  const [focused, setFocused] = useState<DragTarget>(null);

  const rows = phi?.length ?? 0;
  const cols = rows > 0 && phi ? phi[0].length : 0;
  const cellW = cols > 0 ? SVG_WIDTH / cols : 0;
  const cellH = rows > 0 ? SVG_HEIGHT / rows : 0;

  // Precompute the heatmap <rect> list so React doesn't allocate per render
  const heat = useMemo(() => {
    if (!phi || rows === 0 || cols === 0) return null;
    const out: { key: string; x: number; y: number; fill: string }[] = [];
    for (let ri = 0; ri < rows; ri++) {
      for (let ci = 0; ci < cols; ci++) {
        out.push({
          key: `${ri}-${ci}`,
          x: ci * cellW,
          y: ri * cellH,
          fill: colorForPhi(phi[ri][ci]),
        });
      }
    }
    return out;
  }, [phi, rows, cols, cellW, cellH]);

  // Commit helper
  function commit(
    team: Team,
    index: number,
    newPt: Point,
  ) {
    if (team === "ball") {
      onChange({ attackers, defenders, ball: newPt, changed: "ball" });
      return;
    }
    if (team === "attacker") {
      const next = attackers.slice();
      next[index] = newPt;
      onChange({ attackers: next, defenders, ball, changed: "attacker" });
      return;
    }
    const next = defenders.slice();
    next[index] = newPt;
    onChange({ attackers, defenders: next, ball, changed: "defender" });
  }

  // Global pointermove/up while dragging
  useEffect(() => {
    if (!drag || !svgRef.current) return;
    const svg = svgRef.current;
    function handleMove(e: PointerEvent) {
      if (!drag) return;
      const pt = svgToMetres(e, svg);
      commit(drag.team, drag.index, pt);
    }
    function handleUp() {
      setDrag(null);
    }
    window.addEventListener("pointermove", handleMove);
    window.addEventListener("pointerup", handleUp);
    return () => {
      window.removeEventListener("pointermove", handleMove);
      window.removeEventListener("pointerup", handleUp);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [drag]);

  function startDrag(team: Team, index: number, e: React.PointerEvent) {
    if (disabled) return;
    e.preventDefault();
    setDrag({ team, index });
    setFocused({ team, index });
  }

  function onKeyDown(
    team: Team,
    index: number,
    current: Point,
    e: React.KeyboardEvent,
  ) {
    if (disabled) return;
    const step = e.shiftKey ? 5 : 1;
    let dx = 0;
    let dy = 0;
    if (e.key === "ArrowLeft") dx = -step;
    else if (e.key === "ArrowRight") dx = step;
    else if (e.key === "ArrowUp") dy = -step;
    else if (e.key === "ArrowDown") dy = step;
    else return;
    e.preventDefault();
    const next: Point = {
      x: Math.max(0, Math.min(PITCH_LENGTH, current.x + dx)),
      y: Math.max(0, Math.min(PITCH_WIDTH, current.y + dy)),
    };
    commit(team, index, next);
  }

  const dotTitle = (team: Team, idx: number, p: Point): string =>
    `${team === "ball" ? "Ball" : team === "attacker" ? "Attacker" : "Defender"}${
      team === "ball" ? "" : ` #${idx + 1}`
    } at (${p.x.toFixed(1)} m, ${p.y.toFixed(1)} m). Drag or use arrow keys.`;

  return (
    <svg
      ref={svgRef}
      viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
      className="w-full touch-none select-none rounded bg-pitch"
      role="application"
      aria-label="Scenario pitch — drag players to recompute Φ"
    >
      {/* heatmap underlay */}
      {heat &&
        heat.map((h) => (
          <rect
            key={h.key}
            x={h.x}
            y={h.y}
            width={cellW + 0.5}
            height={cellH + 0.5}
            fill={h.fill}
            opacity={0.7}
          />
        ))}

      {/* pitch markings */}
      <rect
        x={1}
        y={1}
        width={SVG_WIDTH - 2}
        height={SVG_HEIGHT - 2}
        fill="none"
        stroke="white"
        strokeOpacity={0.55}
        strokeWidth={2}
      />
      <line
        x1={SVG_WIDTH / 2}
        y1={0}
        x2={SVG_WIDTH / 2}
        y2={SVG_HEIGHT}
        stroke="white"
        strokeOpacity={0.45}
        strokeWidth={1.5}
      />
      <circle
        cx={SVG_WIDTH / 2}
        cy={SVG_HEIGHT / 2}
        r={SVG_HEIGHT * 0.12}
        fill="none"
        stroke="white"
        strokeOpacity={0.45}
        strokeWidth={1.5}
      />
      {/* final-third markers */}
      <line
        x1={(70 / PITCH_LENGTH) * SVG_WIDTH}
        y1={0}
        x2={(70 / PITCH_LENGTH) * SVG_WIDTH}
        y2={SVG_HEIGHT}
        stroke="white"
        strokeOpacity={0.18}
        strokeDasharray="6 6"
      />
      <line
        x1={(35 / PITCH_LENGTH) * SVG_WIDTH}
        y1={0}
        x2={(35 / PITCH_LENGTH) * SVG_WIDTH}
        y2={SVG_HEIGHT}
        stroke="white"
        strokeOpacity={0.18}
        strokeDasharray="6 6"
      />

      {/* defenders */}
      {defenders.map((p, i) => {
        const { cx, cy } = metresToSvg(p);
        const isFocused = focused?.team === "defender" && focused.index === i;
        return (
          <g
            key={`def-${i}`}
            tabIndex={disabled ? -1 : 0}
            role="button"
            aria-label={dotTitle("defender", i, p)}
            onPointerDown={(e) => startDrag("defender", i, e)}
            onFocus={() => setFocused({ team: "defender", index: i })}
            onBlur={() => setFocused(null)}
            onKeyDown={(e) => onKeyDown("defender", i, p, e)}
            className="cursor-grab focus:outline-none"
          >
            <circle
              cx={cx}
              cy={cy}
              r={DOT_R + (isFocused ? 3 : 0)}
              fill="rgb(245, 70, 149)"
              stroke={isFocused ? "white" : "rgba(0,0,0,0.55)"}
              strokeWidth={isFocused ? 3 : 2}
            />
            <text
              x={cx}
              y={cy + 4}
              textAnchor="middle"
              fontSize="11"
              fontFamily="ui-monospace, SFMono-Regular, monospace"
              fill="white"
              pointerEvents="none"
            >
              {i + 1}
            </text>
          </g>
        );
      })}

      {/* attackers */}
      {attackers.map((p, i) => {
        const { cx, cy } = metresToSvg(p);
        const isFocused = focused?.team === "attacker" && focused.index === i;
        return (
          <g
            key={`atk-${i}`}
            tabIndex={disabled ? -1 : 0}
            role="button"
            aria-label={dotTitle("attacker", i, p)}
            onPointerDown={(e) => startDrag("attacker", i, e)}
            onFocus={() => setFocused({ team: "attacker", index: i })}
            onBlur={() => setFocused(null)}
            onKeyDown={(e) => onKeyDown("attacker", i, p, e)}
            className="cursor-grab focus:outline-none"
          >
            <circle
              cx={cx}
              cy={cy}
              r={DOT_R + (isFocused ? 3 : 0)}
              fill="rgb(74, 222, 128)"
              stroke={isFocused ? "white" : "rgba(0,0,0,0.55)"}
              strokeWidth={isFocused ? 3 : 2}
            />
            <text
              x={cx}
              y={cy + 4}
              textAnchor="middle"
              fontSize="11"
              fontFamily="ui-monospace, SFMono-Regular, monospace"
              fill="black"
              pointerEvents="none"
            >
              {i + 1}
            </text>
          </g>
        );
      })}

      {/* ball */}
      {(() => {
        const { cx, cy } = metresToSvg(ball);
        const isFocused = focused?.team === "ball";
        return (
          <g
            tabIndex={disabled ? -1 : 0}
            role="button"
            aria-label={dotTitle("ball", 0, ball)}
            onPointerDown={(e) => startDrag("ball", 0, e)}
            onFocus={() => setFocused({ team: "ball", index: 0 })}
            onBlur={() => setFocused(null)}
            onKeyDown={(e) => onKeyDown("ball", 0, ball, e)}
            className="cursor-grab focus:outline-none"
          >
            <circle
              cx={cx}
              cy={cy}
              r={DOT_R - 2 + (isFocused ? 2 : 0)}
              fill="white"
              stroke="black"
              strokeWidth={2}
            />
          </g>
        );
      })()}
    </svg>
  );
}
