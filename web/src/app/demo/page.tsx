"use client";

import Link from "next/link";
import { useState } from "react";

type Step = {
  title: string;
  body: string;
  href: string;
  cta: string;
};

type Story = {
  key: string;
  headline: string;
  one_liner: string;
  problem: string;
  what_youll_see: string;
  steps: Step[];
};

const STORIES: Story[] = [
  {
    key: "match-debrief",
    headline: "I just finished watching a match — what happened?",
    one_liner:
      "A coach wants a debrief in football language, not a stat table.",
    problem:
      "You&apos;ve watched Qatar 0-2 Ecuador from the 2022 World Cup. Your assistant wants a one-paragraph debrief before tomorrow&apos;s session: who controlled, who carried, who broke play up, who finished.",
    what_youll_see:
      "The match page leads with a coach headline (e.g. &apos;Ecuador controlled territorial threat over Qatar&apos;), two team cards with summary sentences + role-tagged top performers, and the raw per-player event tables tucked behind an Analyst view.",
    steps: [
      {
        title: "Browse real open-data matches",
        body: "Pick the StatsBomb competition → season → match. We wired the adapter to the live StatsBomb open-data GitHub.",
        href: "/matches",
        cta: "Open match browser",
      },
      {
        title: "Jump straight to Qatar 0-2 Ecuador",
        body: "We&apos;ve pre-loaded this World Cup 2022 fixture as the demo match. Read the coach headline and the role-tagged top performers for each side.",
        href: "/matches/match/3857286",
        cta: "Open the match narrative",
      },
    ],
  },
  {
    key: "find-press-resistant-dm",
    headline: "I need a press-resistant DM under €25M",
    one_liner:
      "Scouting in plain English — role + style + budget, not feature sliders.",
    problem:
      "Your number 6 left. You want a press-resistant replacement — someone who keeps the ball under pressure, progresses it, and can dig out of trouble. Under €25M, ideally under 30.",
    what_youll_see:
      "The recruit page takes the brief, picks the criteria and weights for you, runs WASPAS across the synthetic cohort, and ranks the DMs with a one-line &apos;why they fit&apos; verdict each.",
    steps: [
      {
        title: "Open the recruit brief",
        body: "Role = DM, Playstyle = Press-resistant, max age 30, max value €25M.",
        href: "/recruit",
        cta: "Open recruit page",
      },
      {
        title: "Drill into the top candidate",
        body: "Click the top card on the shortlist to see the player&apos;s archetype label, coach-facing style sentence, and nearest neighbors in the cohort.",
        href: "/scouting",
        cta: "Open scouting",
      },
    ],
  },
  {
    key: "build-pressing-xi",
    headline: "Build me a pressing XI on €800M",
    one_liner: "Pick a philosophy, get an XI — not a 5×5 Saaty matrix.",
    problem:
      "You want to field a press-heavy XI across the full 4-2-3-1 on an €800M budget with ≤6 foreigners. You don&apos;t want to hand-tune a pairwise matrix &mdash; you just want to say &apos;press-heavy&apos; and see the team.",
    what_youll_see:
      "The squad page has four preset philosophies (Press-heavy / Possession / Direct / Balanced). Click one, the BIP solves, and you get the optimal XI with total quality score, budget used, foreign count, and any remaining positional gap. The raw AHP matrix is one click away in Analyst view.",
    steps: [
      {
        title: "Apply the press-heavy preset",
        body: "Land on /squad with the preset pre-selected — the BIP runs automatically and the XI fills in.",
        href: "/squad?preset=press_heavy",
        cta: "Open squad with press-heavy preset",
      },
      {
        title: "Watch the tape end-to-end",
        body: "Drop a single-camera broadcast clip into Tape view; see detections projected onto the 105×68 m pitch with a coach readout on team shape.",
        href: "/cv",
        cta: "Open tape view",
      },
    ],
  },
];

export default function DemoPage() {
  const [open, setOpen] = useState<string>(STORIES[0].key);

  return (
    <div className="max-w-5xl">
      <h1 className="text-3xl font-semibold">Guided tour</h1>
      <p className="mt-2 max-w-3xl text-white/60">
        Three coach-level questions AthletIQ answers end-to-end. Pick one to
        walk through the screens; each step links directly to the relevant page
        with the context pre-loaded.
      </p>

      <div className="mt-8 grid grid-cols-1 gap-3">
        {STORIES.map((s) => {
          const isOpen = open === s.key;
          return (
            <div
              key={s.key}
              className={`rounded-lg border transition ${
                isOpen
                  ? "border-accent/50 bg-white/5"
                  : "border-white/10 bg-white/[0.03]"
              }`}
            >
              <button
                type="button"
                onClick={() => setOpen(isOpen ? "" : s.key)}
                className="w-full px-5 py-4 text-left"
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-base font-medium">{s.headline}</div>
                    <div className="mt-0.5 text-xs text-white/50">
                      {s.one_liner}
                    </div>
                  </div>
                  <div className="text-xs text-accent">
                    {isOpen ? "collapse" : "expand →"}
                  </div>
                </div>
              </button>
              {isOpen && (
                <div className="border-t border-white/10 px-5 py-4">
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <div>
                      <div className="text-xs font-medium uppercase tracking-wide text-white/50">
                        Problem
                      </div>
                      <p className="mt-1 text-sm text-white/80">{s.problem}</p>
                    </div>
                    <div>
                      <div className="text-xs font-medium uppercase tracking-wide text-white/50">
                        What you&apos;ll see
                      </div>
                      <p className="mt-1 text-sm text-white/80">
                        {s.what_youll_see}
                      </p>
                    </div>
                  </div>

                  <div className="mt-5 text-xs font-medium uppercase tracking-wide text-white/50">
                    Walkthrough
                  </div>
                  <ol className="mt-2 space-y-3">
                    {s.steps.map((step, i) => (
                      <li
                        key={step.href}
                        className="flex flex-col gap-2 rounded border border-white/10 bg-black/20 p-3 sm:flex-row sm:items-center sm:justify-between"
                      >
                        <div>
                          <div className="text-sm font-medium">
                            {i + 1}. {step.title}
                          </div>
                          <div className="mt-0.5 text-xs text-white/60">
                            {step.body}
                          </div>
                        </div>
                        <Link
                          href={step.href}
                          className="shrink-0 rounded bg-accent/20 px-3 py-1.5 text-xs font-medium text-accent hover:bg-accent/30"
                        >
                          {step.cta} →
                        </Link>
                      </li>
                    ))}
                  </ol>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
