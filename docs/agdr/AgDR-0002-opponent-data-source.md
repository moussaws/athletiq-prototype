---
id: AgDR-0002
timestamp: 2026-04-19T00:00:00Z
agent: claude
model: claude-opus-4-7
trigger: user-prompt (/decide)
status: executed
---

# Opponent data source for the Counterfactual Lab — v1 vs v2

> In the context of the Counterfactual Lab redesign (athletiq-prototype#25, IDEA-001), facing the need for opponent match data to build the Pillar 1 opponent profiles, I decided **StatsBomb Open Data for v1 (prototype + internal demos only) and a paid event-data feed for v2 (commercial launch)**, to achieve a fast, low-cost path to a credible v1 demo while explicitly fencing the non-commercial license risk, accepting a forced provider migration before any commercial release and v1 coverage limited to the competitions the open dataset includes.

## Context

- Pillar 1 of the Lab redesign requires a real opponent model built from each opponent's actual recent matches (positional heatmaps, pressing intensity per zone, defensive line height distribution, transition speed, set-piece tendencies). The current code has only formation presets (`metrics/scenario.py:_preset_attacker`) — generic, opponent-agnostic.
- StatsBomb provides two product tiers: **Open Data** (CC BY-NC-SA 4.0, free, GitHub-hosted, selected competitions) and **StatsBomb Pro** (commercial, full league coverage, contractual data-handling).
- `pyproject.toml` already declares `statsbombpy>=1.13,<2` as an optional `[statsbomb]` extra — Open Data ingestion is two `pip install` flags away.
- Athletiq is a commercial product. Any commercial launch — including freemium / trial-into-paid funnels — using StatsBomb Open Data as the production data path is a license breach (the NC clause is unambiguous and StatsBomb actively enforces it).
- v1 audience is **internal demos + design partnerships with friendly clubs**, not paying customers. v2 is the first surface a paying customer touches.

## Options Considered

| Option | Pros | Cons |
|--------|------|------|
| **A — StatsBomb Open as v1, paid feed by v2 (chosen)** | Two `pip` flags away; well-documented; tooling (`statsbombpy`) already a declared optional dep; gets a credible demo to a coach in days, not months; same vendor's commercial tier means schema continuity at v2 migration time → minimal model-layer rewrite. | NC license forces a hard pre-commercial-launch gate that must not be skipped; v1 cannot demo current Premier League ("vs Man City — last 6 PL matches"), only competitions the open dataset includes. |
| **B — StatsBomb Open as v1, build our own ingestion via Pillar C CV by v2** | Strategic moat — Athletiq's own CV becomes the production data source, not a third-party feed; lowest long-run cost; full control over schema; differentiator vs every competitor reselling StatsBomb. | Pillar C is months of work and currently a research prototype, not a production ingestion pipeline; couples two ambitious roadmaps (Lab redesign + production-grade CV); v2 slips significantly if CV slips. |
| **C — Skip Open, contract paid from day one (StatsBomb Pro / Wyscout / Opta)** | Single data source from v1 → no migration; full coverage from the start (current PL, etc.); commercially clean. | Contract negotiation takes weeks-to-months; meaningful annual cost (£5k–£50k depending on coverage / vendor) before product-market fit is established; v1 demo timeline pushed out. |
| **D — Synthetic opponents only (extend `data/synthetic.py`)** | Zero data-licensing risk; instant; deterministic; reproducible for unit tests. | A synthetic "opponent" is no opponent at all — exactly the gap the critique flags as the #1 reason the Lab is not useful today. Defeats the point of Pillar 1. |

## Decision

Chosen: **Option A — StatsBomb Open Data for v1 (internal/demo only), paid feed for v2 (commercial launch)**, because:

1. **Speed-to-credible-demo dominates v1.** The whole purpose of v1 is to put the Lab in front of a real coach and test whether the prescription layer (Pillar 4) is actually useful. Anything that delays that test by more than days is the wrong choice.
2. **Schema continuity at v2 migration**. If we stay in-vendor (StatsBomb Open → StatsBomb Pro), the data model layer barely changes — the migration is licensing + endpoint switching, not a rewrite. Going Open → a different vendor at v2 wastes the v1 investment.
3. **The license risk is real but boundable** with a hard pre-launch gate (see Consequences). The risk only materialises if someone forgets to flip the switch — that's a process problem, solved with a gate, not an architecture problem.
4. **Option B's payoff is real but its risk is intolerable for v1.** Coupling the Lab redesign timeline to production-grade Pillar C CV means both slip together. Park B as a v3+ moat play.

## Consequences

### Mechanical / engineering

- **Add the `[statsbomb]` extra to the default install path** for any contributor working on Lab Pillar 1 — currently optional. Document in the project README.
- **Build the v1 ingester as feed-agnostic from day one**: a `src/athletiq/data/opponents/` module with a `OpponentEventStore` interface, and `StatsBombOpenStore` as the first implementation. v2's `StatsBombProStore` (or `WyscoutStore`, etc.) implements the same interface, so the Lab + LLM prescription layer never see the raw vendor schema. **This is the single most important consequence — getting the abstraction right at v1 is what makes v2 a swap, not a rewrite.**
- **Coverage choice for v1 demo**: pick 2–3 opponents that are both well-covered in StatsBomb Open AND tactically distinctive enough that a coach watching the demo immediately recognises the model is working. Strong candidates: Atlético (block-and-counter, La Liga 2015–2020 coverage), Bayer Leverkusen (Xabi 2023-24 if covered), an Euros 2024 side. Pick during PRD scoping.

### Process / non-engineering

- **Hard pre-launch gate (mandatory)**: the Pillar 1 ingester ships with an `ATHLETIQ_LICENSE_TIER` env var checked on every opponent-data read. `tier=open` is allowed only when `ATHLETIQ_ENV in {"dev", "demo", "internal"}`. Production environments require `tier=paid`. The check fails closed — if either var is unset, no data loads. Add this to the v1 PR, not v2.
- **Pre-commercial-launch checklist item**: "StatsBomb Open Data fully removed from production data path; all reads go via the paid-feed implementation". Owned by Tech Lead. Lives in the launch-readiness rubric (`/launch-check`).
- **License attribution in v1 demo surface**: every opponent profile rendered while running on Open Data carries a small "StatsBomb Open Data — CC BY-NC-SA 4.0" line. Demos to coaches see it; if a coach asks about commercial use, we have an honest answer ready.
- **Triage today, decide v2 vendor 60 days before commercial launch**: when v2 nears, this decision becomes "StatsBomb Pro vs Wyscout vs Opta" — out of scope here. New AgDR at that time.

### Strategic

- **Option B is parked, not killed.** The roadmap should have a v3+ entry: "production-grade Pillar C CV → replace third-party event feed with our own tracking output". When that ships, we drop the paid feed and own the moat. AgDR-0002 explicitly does not bind that decision.
- **Cost line**: v1 = £0 in data costs. v2 paid feed budget needs to be in the commercial-launch financial plan; rough order-of-magnitude £5k–£50k/year depending on competitions covered.

## Artifacts

- Tracker: athletiq-prototype#25 (parent — Counterfactual Lab redesign)
- Companion AgDR: AgDR-0001 (LLM provider — Anthropic Claude)
- Backlog: `projects/athletiq-prototype/lab-critique.md` § Pillar 1 (in the apexyard ops repo)
- Implementation: TBD — first PR scaffolds `src/athletiq/data/opponents/` interface + `StatsBombOpenStore` + `ATHLETIQ_LICENSE_TIER` gate
- License source: https://github.com/statsbomb/open-data — README pins CC BY-NC-SA 4.0

---

## Footnote — verified open-data coverage shape (added 2026-04-19)

The "candidate opponents" line above (Atlético / Bayer / Euro 2024 side) was the original guess at AgDR creation time. The PRD-stage open-data verification (run live via `statsbombpy.sb.competitions()` + per-competition `sb.matches()`) found the actual shape is **different in one important way** from that guess:

| Original guess | Verified reality (2026-04-19) | Verdict |
|---|---|---|
| Atlético Madrid La Liga 2018-19 | StatsBomb Open's La Liga coverage is **Barcelona-centric** — only 2 matches per Atlético per season (the two Clásicos vs Barça). Not enough for a profile. | ❌ Drop |
| Bayer Leverkusen Bundesliga 2023-24 | **Full season — 34 matches.** Bundesliga 2023-24 IS in open data, contrary to my prior assumption that Bundesliga was absent. | ✅ Keep |
| A Euro 2024 side | Confirmed — Euro 2024 has 51 matches; Spain (the eventual winners) play 7. | ✅ Keep |

**Implication for the v1 opponent picks**: **Bayer Leverkusen 2023-24** + **Spain Euro 2024**. Tactically distinct, very fresh data, both well-covered.

**Implication for the decision itself**: none — Option A still wins on the same reasoning. The footnote exists so the next person reading this AgDR doesn't repeat the Atlético mistake based on the original example list.

**General rule for future use**: StatsBomb Open's per-team coverage is *competition-centric, not team-centric*. La Liga = Barcelona-focused; Bundesliga 2023-24 = full season; tournaments (Euros, World Cups) = full coverage of all teams. Verify with `sb.matches()` before committing to any team-level v1 demo plan.
