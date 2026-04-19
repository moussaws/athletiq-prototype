import ScenarioLab from "./ScenarioLab";

export const dynamic = "force-dynamic";

export default function LabPage() {
  return (
    <div className="max-w-6xl">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="font-display text-4xl font-semibold tracking-tightest text-white">
          Tactical Counterfactual Lab
        </h1>
        <span className="chip chip-accent">
          <span className="h-1.5 w-1.5 animate-pulse-soft rounded-full bg-accent" />
          <span className="normal-case tracking-normal">Preview</span>
        </span>
      </div>
      <p className="mt-2 max-w-3xl text-white/60">
        Drag a defender, shift the back line, switch formation — the
        pitch-control surface Φ recomputes on every edit. This is the
        first-of-its-kind interactive version of the counterfactual Φ read
        baselined by Umemoto &amp; Fujii (2023) on Spearman (2018)&apos;s
        continuous-space formulation; we productized it, we did not invent it.
        Diff cards, player-swap and share-links ship in the next PRs.
      </p>

      <div className="mt-8">
        <ScenarioLab />
      </div>

      <footer className="mt-10 border-t border-white/5 pt-4 text-2xs text-white/40">
        Prior art credited: Umemoto &amp; Fujii (StatsBomb, 2023) — offline
        counterfactual Φ baseline; Spearman (2018) — continuous-space pitch
        control. Our contribution is the interactive, coach-facing product
        surface, not a new algorithm.
      </footer>
    </div>
  );
}
