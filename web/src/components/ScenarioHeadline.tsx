"use client";

import type { ScenarioDiff } from "@/lib/api";

/**
 * Prominent banner above the pitch that renders the backend-generated
 * coach headline (``diff.headline``). When nothing has been edited yet we
 * render an inviting call-to-action instead so the page never looks empty.
 *
 * Keeping the verdict text generation on the server (see
 * ``metrics/scenario.py::auto_headline``) means the diff cards and the
 * headline can never drift out of sync — both read the same payload.
 */
export type ScenarioHeadlineProps = {
  diff: ScenarioDiff | null;
  edited: boolean;
  recomputing: boolean;
};

export default function ScenarioHeadline({
  diff,
  edited,
  recomputing,
}: ScenarioHeadlineProps) {
  const hasHeadline = diff !== null && diff.headline.trim().length > 0;

  if (!edited || !hasHeadline) {
    return (
      <div
        className="rounded border border-dashed border-white/15 bg-white/5 px-4 py-3 text-sm text-white/60"
        aria-live="polite"
      >
        Drag a defender, nudge the line, or pick a different formation to see
        the Φ delta, territorial balance, and a plain-English coach verdict
        update in real time.
      </div>
    );
  }

  return (
    <div
      className={`flex items-start gap-3 rounded border border-accent/30 bg-accent/5 px-4 py-3 text-sm text-white transition-opacity ${
        recomputing ? "opacity-70" : "opacity-100"
      }`}
      role="status"
      aria-live="polite"
    >
      <span
        aria-hidden
        className="mt-[3px] inline-block h-2 w-2 shrink-0 rounded-full bg-accent"
      />
      <p className="leading-snug text-white">{diff!.headline}</p>
    </div>
  );
}
