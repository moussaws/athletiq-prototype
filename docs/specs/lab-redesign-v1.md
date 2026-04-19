# PRD: Counterfactual Lab v1 — Coach-Credible Foundation

**Status**: Draft
**Author**: Mohamed Samy Moussa (Product Manager hat)
**Created**: 2026-04-19
**Last Updated**: 2026-04-19
**Tracker**: [athletiq-prototype#25](https://github.com/moussaws/athletiq-prototype/issues/25)
**Backlog**: IDEA-001
**Related**: `projects/athletiq-prototype/lab-critique.md` (the critique this PRD is scoped against), `docs/agdr/AgDR-0001` (LLM provider), `docs/agdr/AgDR-0002` (opponent data source)

---

## Overview

### Problem Statement

The current Counterfactual Lab (`/lab`) is a kinematics sandbox dressed up as a tactical tool. A working manager who opens it gets:

1. A page that shows nothing useful until they manually drag a dot.
2. A "defender" that is the attacker's formation mirrored across halfway — **not** the team they actually play next Saturday.
3. A lineup picker that tells them, in writing, that *"Φ math is unaffected"* — Haaland in the 9 changes literally zero numbers.
4. A coach-facing surface littered with `Φ`, `Δ`, `34 × 52 grid`, and academic citations to Spearman 2018.

The critique (see `lab-critique.md` §2) catalogues 12 gaps. v1 closes the four that immediately disqualify the product when shown to a real coach: **no opponent**, **no player effect**, **no landing insight**, **no coach vocabulary**. Pillar 4 (prescriptive instruction generation), Pillar 5 (side-by-side + playbook), and Pillars 6–8 are deliberately deferred — they all depend on this foundation being credible first.

### Target User

**Primary**: assistant coach / performance analyst at a top-tier European club, preparing on a Friday for Sunday's match. Wants to load *their* next opponent, run *their* probable XI against it, and see what changes vs. their default approach.

**Secondary**: head of recruitment / sporting director, using the Lab as the validation surface for a Pillar B scouting candidate ("if I sign this 23-year-old left-back, how does our shape change vs the three opponents we've struggled against?").

**Internal**: Athletiq's own team running design-partner demos. v1 success means a demo we can run end-to-end without the coach asking *"yeah but what does this actually do?"*

### Goals (measurable)

1. **Lineup actually moves the numbers.** Today: 0% of swaps change Φ or xG. v1: 100% of swaps move at least one diff-card value visibly.
2. **At least 2 real opponent profiles** selectable from a dropdown. Today: 0.
3. **Zero Greek letters / academic jargon** on the default `/lab` coach surface. Today: 8+ instances. (They live in the Analyst view instead.)
4. **Baseline insight rendered on landing**, no user action required. Today: empty placeholder until first drag.
5. **Time-to-first-meaningful-insight on `/lab` ≤ 5 seconds** from page load. Today: ∞ (requires drag).

### Non-Goals (Out of Scope)

- **Pillar 4 prescriptive instruction generator**. Separate PRD; depends on this v1 + AgDR-0001 (Claude). Without v1's opponent + player models, prescriptions are noise.
- **Full Premier League / current-season opponent coverage.** Blocked by AgDR-0002 (StatsBomb Open is the v1 source, paid feed is v2). v1 ships 2–3 opponents that the open dataset covers well.
- **Real confidence intervals.** Placeholder pill only in v1 (Phase 7 in the roadmap is the real implementation).
- **Side-by-side multi-scenario comparison + per-opponent saved playbooks.** Phase 5.
- **Video / clip-anchored counterfactuals.** Phase 6.
- **Learned (TacticAI-class) counterfactuals.** Phase 8.
- **Mobile-optimised UI.** Desktop browser is the v1 target — this is a Friday-match-prep surface.
- **Multi-tenancy / club isolation.** Demo + internal-only at v1; no paying customers yet (per AgDR-0002).

---

## User Stories

1. As an **assistant coach preparing for Sunday's Atlético match**, I want to select Atlético from an opponent dropdown so I can experiment against their actual defensive posture, not a generic 4-3-3 mirror.
2. As an **assistant coach**, I want my chosen lineup to change the simulation so the player names matter, not just the dot positions.
3. As an **assistant coach**, I want the Lab to show me a useful insight about my opponent the moment the page loads so I'm not staring at *"drag a defender to see…"*.
4. As a **head of recruitment looking at a scouting candidate**, I want to drop them into our XI in the Lab against our next opponent and see how our shape changes, so I can connect "should we sign them?" to "how do they help us **next**?"
5. As an **Athletiq engineer running a design-partner demo**, I want a coach-facing surface free of `Φ`, `Δ`, and academic citations so the coach doesn't disqualify the product in the first 30 seconds.
6. As an **Athletiq operator**, I want production data reads to fail closed when `ATHLETIQ_LICENSE_TIER ≠ paid`, so we cannot accidentally ship the StatsBomb Open Data path to a paying customer (per AgDR-0002).

---

## Requirements

### Must-Have (P0)

#### Data layer (Pillar 1 + Pillar 2 of the critique)

- **`OpponentEventStore` interface** in `src/athletiq/data/opponents/` — feed-agnostic abstraction so v2's paid feed is a swap, not a rewrite. The Lab and the LLM prescription layer (future) only ever see the abstraction's domain types, never raw vendor schemas.
- **`StatsBombOpenStore` implementation** behind that interface, using the existing `statsbombpy` optional extra (now mandatory for the Lab module).
- **`ATHLETIQ_LICENSE_TIER` env-var gate** that fails closed: `tier=open` is allowed only when `ATHLETIQ_ENV ∈ {dev, demo, internal}`. Production envs require `tier=paid`. Both vars unset → no opponent data loads. Tested with a unit test that asserts the closed-fail behaviour.
- **`OpponentProfile` domain type**: `(positional_heatmap, pressing_intensity_per_zone, def_line_height_distribution, formation_mix, transition_speed_proxy, source_attribution_text)`. The minimum viable shape to drive Pillar 1 of the critique.
- **2 opponent profiles built and committed**: candidates per AgDR-0002 — Atlético (block-and-counter, La Liga 2015–2020 coverage), Bayer Leverkusen 2023-24 (if covered), or an Euro 2024 side. Final 2-of-3 pick happens before the first PR.
- **Per-player tactical profile** ingested from FBRef. Stored as `PlayerProfile`: `(pressing_pct, progressive_pass_pct, aerial_duel_win_pct, finishing_pct)` — all derivable from FBRef per-90 counts via percentile rank within the position pool. Kinematic absolute units (`max_speed_ms`, `max_accel_ms2`) are **deferred** to a future phase that lands a real tracking source — verified against `src/athletiq/data/fbref.py:9-15` which states FBRef does not publish tracking-derived signals. See resolved Open Question #2.

#### Math layer

- **`phi_from_positions` stays unchanged in v1**: TTI keeps the existing global kinematic constants. The "lineup actually moves the numbers" requirement is met entirely via the `scenario_xg` change below, not via Φ. Per-player TTI conditioning re-enters the roadmap when a real tracking source lands (post-AgDR-0002 v2 paid feed, or our own Pillar C CV when production-grade).
- **`scenario_xg` becomes player-conditional**: weights shot quality by the attacking-side striker's `finishing_pct` and weights defensive recovery by defender's `pressing_pct + aerial_duel_win_pct`. Backwards compatible — when profiles are absent (preset-only scenario), the existing generic constants are used. **This is the single lever that fixes the "Haaland changes nothing" bug in v1.**
- **Compute budget unchanged**: 34×52 grid, single scenario, p95 ≤ 100 ms on the dev hardware (current). Per-player conditioning must not regress this.
- **Defender preset replacement**: when an opponent is selected, defender dot positions are sampled from the opponent's actual formation-mix distribution + def-line-height distribution. Mirrored-formation preset remains as a fallback when "no opponent selected" is chosen.

#### UI layer (Phase 0 + Phase 2)

- **Opponent selector** on `/lab` — a labelled dropdown above the formation row. Default "No opponent (generic)" mirrors current behaviour.
- **Render baseline insight on landing**: replace the empty `ScenarioHeadline` placeholder with the baseline scenario's actual headline. Engine already computes it.
- **Strip from coach surface**: every instance of `Φ`, `Δ`, `34 × 52 grid`, "Spearman 2018", "Umemoto & Fujii 2023". Diff card titles change from "Φ mean" → "Attack pressure" (or equivalent — design pass needed). The Analyst view (already a `<details>`) keeps the technical labels.
- **Lineup section disclaimer removed**: the `"Lineup travels in the share link; Φ math is unaffected"` line is deleted, because it no longer is unaffected.
- **Confidence pill (placeholder)** rendered next to the headline. Hard-coded text in v1 (e.g. "Confidence: medium — based on opponent's last 6 matches"). Real CIs are Phase 7.
- **License attribution** below the opponent selector when an open-data opponent is loaded: `"StatsBomb Open Data — CC BY-NC-SA 4.0"`.

#### Non-functional

- **Backwards compatibility**: existing `?s=…` share-link encoding continues to load (with the mirrored-formation defender). Adds an `?opp=<slug>` param when an opponent is selected.
- **Feature flag**: ship behind `?v=2` on `/lab` for the first 1–2 design-partner sessions, then default-on once we've validated. `?v=1` keeps the current Lab available as a fallback.
- **Tests**: per-player conditioning has at least one unit test per math function changed; `StatsBombOpenStore` has a fixture-driven integration test; `ATHLETIQ_LICENSE_TIER` gate has the closed-fail test described above.

### Nice-to-Have (P1)

- **4 opponents** instead of 2.
- **Per-player physical profile shown on hover** in the lineup section (max speed, age, percentiles).
- **Opponent's last-5-matches form** rendered next to the profile (W/D/L strip).
- **"Reset to opponent baseline" button** distinct from "Reset to formation preset" — switches between "the opponent's typical posture" and "the textbook formation".
- **`/scouting/[id] → /lab?opp=<slug>` deep link** that drops the candidate into our XI against a chosen opponent. The Pillar A × Pillar B bridge in concrete form.

### Future (P2 — not in this PRD)

Everything in critique §6 Phases 3–8. Logged in the roadmap; separate PRDs as they activate.

---

## Success Metrics

### Leading Indicators (days–weeks)

- **Lineup-changes-the-numbers**: % of internal demo sessions where a player swap moves at least one diff-card value visibly. Target: **100%** (currently 0%).
- **Time-to-first-meaningful-insight**: time from page load to a visible non-placeholder headline. Target: **≤ 5 s p95** (currently ∞).
- **Opponent-profile load latency**: time from opponent dropdown selection to defender dots re-rendered. Target: **p95 ≤ 1 s**.
- **Compute regression check**: `phi_from_positions` p95 latency post-Phase-1 vs pre-Phase-1. Target: **no regression beyond +10%**.
- **Demo cadence**: design-partner / internal demo sessions per week. Target: **≥ 2/week** by end of Phase 2.

### Lagging Indicators (weeks–months)

- **Design-partner clubs actually running match prep on the Lab**. Target: **1 by end of quarter, 3 by end of next quarter**. Pulled from session logs + qualitative confirmation from each club's contact.
- **Coach feedback after 4 sessions** (qualitative + 1–10 score on the question *"would you use this again before next week's match?"*). Target: **median ≥ 7** across design partners.
- **Unique opponents loaded per session** (proxy for prep depth — are they exploring multiple options or just opening one and bouncing?). Target: **median ≥ 2 per session** in regular use.
- **Pillar 4 unblocked**: a Phase 4 PRD can be written and started with confidence that the foundation it sits on is real. Binary outcome.

---

## Open Questions

1. ~~**Which 2 (or 3) opponents do we ship for v1?**~~ **RESOLVED 2026-04-19**: **Bayer Leverkusen Bundesliga 2023-24** (34 matches, full Xabi Alonso unbeaten campaign) and **Spain Euro 2024** (7 matches, full tournament including the final). Verified live against `statsbombpy.sb.matches()`. Atlético — the original AgDR-0002 candidate — was dropped because StatsBomb Open's La Liga coverage is Barcelona-centric (only 2 Atlético matches per season). See AgDR-0002 footnote.
2. ~~**FBRef physical data — absolute units or derived percentiles?**~~ **RESOLVED 2026-04-19**: Neither — **dropped from v1 entirely**. `src/athletiq/data/fbref.py:9-15` confirms FBRef publishes no tracking-derived signals (sprint counts in the existing CSV are already proxies of on-ball activity, not real GPS). Deriving `max_speed_ms` from those proxies would be honest only with a derivation citation that nobody asked for. v1 conditions on tactical percentiles only — fixes the "Haaland changes nothing" bug via xG weighting. Kinematic absolute units re-enter the roadmap when a real tracking source lands.
3. **Coach contact for early validation.** Pillar 4 prescription quality (a future PRD) lives or dies on this; even v1 benefits from one real coach reviewing the Phase 0 brand cleanup. Who is our first contact? Owner: Mohamed.
4. **Pillar A × Pillar B bridge — v1 or P1?** "Drop scouting candidate into lineup" is the connective tissue. P1 in this PRD; could be promoted to P0 if a design partner explicitly asks. Owner: triage call.
5. **Brand cleanup political risk.** Stripping `Φ` from the coach surface may be contested by the research-mode users (the academic citation footer is currently a brand asset for technical credibility). Need explicit sign-off — Mohamed + research lead — before Phase 0 PR lands. Mitigation: keep the citations + Greek letters in the Analyst view (`<details>` block), so we lose nothing for the research audience.
6. **StatsBomb Open coverage of "set-piece tendencies".** Critique §4 Pillar 1 lists set-piece tendencies in the opponent profile. Open data may not have enough; if not, drop from v1's `OpponentProfile` shape and add when we have the paid feed (AgDR-0002 v2).

---

## Timeline

Single-engineer wall-clock estimates. Multi-engineer reduces proportionally.

| Phase | Scope | Effort | Deliverable |
|---|---|---|---|
| **Phase 0** | Foundation cleanup — baseline-on-landing, strip Greek letters from coach surface, confidence pill placeholder, lineup disclaimer removal, feature flag wiring | **3–5 days** | `/lab?v=2` ships with the cosmetic fixes. Demoable end-of-week. |
| **Phase 1** | Player tactical profile — `PlayerProfile` schema (tactical percentiles only, no kinematic absolutes per resolved Open Q #2), FBRef percentile ingestion, `scenario_xg` goes player-conditional, lineup actually moves the numbers | **4–6 days** | Brand-promise restored; the lineup section is no longer cosmetic. |
| **Phase 2** | Opponent profile v0 — `OpponentEventStore` interface, `StatsBombOpenStore`, `ATHLETIQ_LICENSE_TIER` gate, **Bayer Leverkusen 2023-24 + Spain Euro 2024** shipped, opponent selector UI, defender preset replacement | **10–14 days** | First end-to-end demo we can run with a real coach. |
| **Total** | | **2.5–4 weeks** | v1 ready for the first design-partner session. |

P1 items (extra opponents, scouting deep link, hover details) add another **3–5 days** if pulled in.

### Dependencies / blockers

- **No blockers on AgDR-0001 (Claude)** — Pillar 4 is out of scope for v1, so the LLM dep doesn't activate yet.
- **AgDR-0002 (StatsBomb Open) is fully cleared** for v1 internal/demo use; the `ATHLETIQ_LICENSE_TIER` gate is itself a P0 deliverable here.
- **FBRef ingestion** is straightforward (percentile rank within position pool from existing per-90 columns); Open Question #2 resolved in favour of skipping kinematic absolutes entirely.
- **Design pass** for Phase 0 brand cleanup — at minimum, the coach-facing labels for the diff cards need a non-jargon rename. Could be done by Mohamed or activate UI Designer per role-triggers.

### Rollout

- **Week 1**: Phase 0 ships behind `?v=2`. Internal demo end-of-week.
- **Week 2–3**: Phase 1 lands; internal team uses `?v=2` exclusively for any Lab work.
- **Week 4–5**: Phase 2 lands; first external design-partner session.
- **End of Week 5**: `?v=2` becomes default if external feedback is ≥ neutral. `?v=1` retained as a one-line escape hatch for one further sprint, then deleted.

---

## Open issues / handoff notes

- This PRD hands off to the **Tech Lead** for the technical-design phase per `.claude/rules/role-triggers.md`. The technical design needs to make the per-player math change concrete (which kernel parameters become per-player; what defaults are used when a profile is missing) and pin the `OpponentEventStore` interface shape.
- Once tech design is approved, break P0 requirements into individual story tickets in `moussaws/athletiq-prototype` GitHub Issues, all linked to athletiq-prototype#25.
- Phase 0 is small enough to be a single PR; Phase 1 is 2–3 PRs (schema, ingestion, math); Phase 2 is 3–4 PRs (interface, store, gate, UI).
