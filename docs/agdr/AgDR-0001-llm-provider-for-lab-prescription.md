---
id: AgDR-0001
timestamp: 2026-04-19T00:00:00Z
agent: claude
model: claude-opus-4-7
trigger: user-prompt (/decide)
status: executed
---

# LLM provider for the Counterfactual Lab prescription layer

> In the context of the Counterfactual Lab redesign (athletiq-prototype#25, IDEA-001), facing the need for an LLM that turns structured Φ/xG diff payloads into coach-facing instructions and risk registers, I decided to standardise on **Anthropic Claude (API)** behind a thin internal abstraction, to achieve best-in-class structured output + tool use + prompt caching at acceptable cost, accepting vendor concentration on a single provider that we'll mitigate via the abstraction layer.

## Context

- Pillar 4 of the Lab redesign requires an LLM that takes a structured payload (`ScenarioDiff`, opponent profile, lineup, phase, game state) and produces (a) a 1-sentence verdict, (b) a bulleted instruction list in coach vocabulary, (c) a risk register. Output must be reliably structured (JSON-schema or tool-call shape) so the UI can render diff cards, risk pills, and printable team sheets without parsing prose.
- Throughput pattern: a manager preparing for the next match runs ~10–50 scenarios in a session against the same opponent profile + same season-to-date team data. The opponent profile is large (multi-match heatmaps, pressing maps, set-piece tendencies) and **repeats verbatim across every scenario in the session**.
- Latency target: pre-match prep, not in-game. Sub-5 s per scenario is comfortable; sub-2 s is desirable.
- Privacy: opponent data from paid feeds (StatsBomb, Wyscout) and club partnerships may be subject to no-training / no-retention contractual terms. The provider's data-handling defaults must support that without per-deal custom contracting.
- Team capacity: 4 engineers. We cannot afford to maintain a self-hosted inference stack while also building the product.
- Existing repo state: no LLM dependency in `pyproject.toml` today. This decision establishes the first one.

## Options Considered

| Option | Pros | Cons |
|--------|------|------|
| **A — Anthropic Claude (API, Sonnet 4.6 + Opus 4.7)** | Best-in-class structured output + tool use; **prompt caching with 5-min TTL** maps perfectly to the per-session opponent-profile reuse pattern (50× cost reduction in our usage shape); 1M-context Opus 4.7 fits a full season of opponent matches; commercial protections (no training on customer data); Anthropic SDK is well-supported. | Single vendor; pricing is at the higher end for Opus; cache-miss cost on cold sessions is material; no native vision API at the same maturity as OpenAI/Gemini (only matters for Pillar 6 video work, which is later). |
| **B — OpenAI GPT-5 (and family)** | Mature ecosystem; strong embeddings + vision (relevant for Pillar 6 / Pillar C CV); slightly cheaper at the smaller tiers; widely available SDKs. | Structured-output reliability has historically lagged Claude tool-use; prompt-caching is automatic but less predictable than Claude's explicit cache_control; data-handling defaults require explicit opt-out paths for some product surfaces. |
| **C — Google Gemini 2.x** | Massive context; strong native vision (would shorten Pillar 6 video work); Google's TacticAI work is the SOTA reference for football counterfactuals — partnership optionality. | Structured-output and tool-use reliability less battle-tested than Claude in 2026; vendor lock-in to Google Cloud for the best pricing; partnership rumour ≠ partnership reality. |
| **D — Self-hosted open-weights (Llama 3.x / Mistral / Qwen 2.5)** | No data egress; predictable cost at scale; required if/when an enterprise club deal demands on-prem. | Quality gap on instruction-generation tasks at the size we could realistically self-host; eats engineering time we don't have (4 people); GPU infra is a separate operational discipline; defer until a deal explicitly requires it. |

## Decision

Chosen: **Option A — Anthropic Claude**, because:

1. **Structured output + tool use is Pillar 4's hardest engineering risk**, and Claude's tool-use + JSON-schema reliability is the strongest in the field on the kind of structured payloads the Lab will produce.
2. **The opponent-profile reuse pattern is a perfect fit for explicit prompt caching** with `cache_control` markers. Manager-prep sessions are exactly the workload prompt caching was built for: large repeated context (opponent profile, lineup, season-to-date stats) + small varying tail (the specific scenario edits). Realistic estimate: 30–50× lower per-scenario cost vs naive completions.
3. **Opus 4.7's 1M context** lets us put a full season of opponent match data in the prompt without RAG, which removes a whole class of retrieval-quality bugs from Pillar 4's first cut.
4. **Anthropic's data-handling defaults** (no training on customer data via the API) make club-partnership contracts shorter and faster to close.
5. **Single-vendor risk is real but manageable**: we wrap every LLM call behind an `AthletiqLLMClient` interface in `src/athletiq/llm/` so swapping a specific feature to OpenAI / Gemini / self-hosted is a config change, not a rewrite.

Default routing within Claude: **Sonnet 4.6** for the standard prescription generator (latency + cost), **Opus 4.7** opt-in for the side-by-side multi-scenario comparator (Pillar 5) where reasoning quality dominates and a single session is OK to cost more.

## Consequences

- **New runtime dependency**: `anthropic` SDK added to `pyproject.toml`. New env var `ANTHROPIC_API_KEY` (must be added to `.env.example` once that file exists — see athletiq-prototype handover assessment risks).
- **New module**: `src/athletiq/llm/` containing the abstraction (`AthletiqLLMClient`, prescription tool schemas, cache-control wiring, retry/backoff). All LLM calls go through it; no direct `from anthropic import …` outside this module.
- **Cost line**: managed-prep workload becomes a real cost line. Need a per-club budget cap + observability to flag runaway sessions. Add to monitoring scope.
- **Cache strategy**: opponent profile + system prompt + lineup get `cache_control: ephemeral`; only the per-scenario diff payload is cache-miss. Session expected to stay within the 5-min TTL during active prep.
- **Security review trigger**: the first Pillar 4 PR that wires user-supplied opponent data to the LLM call will activate the [Security Auditor](../../../../roles/security/security-auditor.md) per `.claude/rules/role-triggers.md` (PII / data-handling boundary). Plan for that gate.
- **No on-prem path until needed**: Option D remains the escape hatch for any club deal that explicitly mandates on-prem; the abstraction makes the swap a few weeks of work rather than a rewrite.
- **Vision deferred to Pillar 6**: when video integration lands, re-evaluate whether to use Claude vision (good enough), Gemini vision (best-in-class for video), or a dedicated CV pipeline. Not blocking for Phases 0–5.
- **No commitment beyond Pillar 4**: Pillar 8 (learned counterfactuals, TacticAI-class) is a deep-net training problem, not an LLM problem. This decision does not bind that.

## Artifacts

- Tracker: athletiq-prototype#25 (parent — Counterfactual Lab redesign)
- Backlog: `projects/athletiq-prototype/lab-critique.md` § Pillar 4 (in the apexyard ops repo)
- Implementation: TBD — first PR will create `src/athletiq/llm/` and add the `anthropic` dep
