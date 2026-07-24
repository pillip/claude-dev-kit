# Research Claim Record

> Used by `/brainstorm` (Existing Landscape) and `/bizanalysis` (Market /
> Competitive / Pricing / Risks) **on the degraded path** — when
> `/deep-research` is not exposed by the runtime. The primary path consumes
> `/deep-research`'s cited report directly; this schema only applies to
> claims the kit constructs itself.
>
> See: SPEC-018, `docs/cache_friendly_authoring.md`, `docs/references/research/`.

## Schema

Every quantitative or factual claim in research output (other than
authored opinion) carries this record:

```json
{
  "quote":        "verbatim text copy-pasted from the captured source",
  "source_url":   "https://example.com/full/path",
  "accessed_at":  "2026-06-18T12:00:00+00:00",
  "published_at": "2025-03-01",
  "slug":         "example-com-full-path"
}
```

Field rules:

| Field           | Required | Notes                                                                                   |
| --------------- | -------- | --------------------------------------------------------------------------------------- |
| `quote`         | yes      | Verbatim text — no paraphrase, no ellipsis, no normalization. Must appear in the captured snapshot. |
| `source_url`    | yes      | Full URL passed to `capture_source.py`. The validator uses it to locate the snapshot.   |
| `accessed_at`   | yes      | ISO-8601 timestamp of when the capture happened. Provided by `capture_source.py` sidecar metadata. |
| `published_at`  | optional | ISO-8601 string of when the source was published. Used for freshness gating. If omitted, the validator consults the snapshot's sidecar metadata. |
| `slug`          | optional | Override the slug derivation. Use only when an explicit override is needed.             |

## Workflow

1. **Capture**: `python3 scripts/capture_source.py <url>` writes
   `docs/references/research/<slug>.html` plus a sidecar
   `<slug>.meta.json`.
2. **Construct**: when authoring a claim, copy the verbatim quote from
   the captured HTML, fill in `source_url` / `accessed_at` from the
   sidecar metadata. Do **not** paraphrase. Do **not** trim leading or
   trailing whitespace inside the quote (the validator is strict).
3. **Validate**: `python3 scripts/validate_research_claim.py
   --claim-file <claim>.json` returns one of `ok` / `quote_missing` /
   `stale` / `snapshot_absent`. Save is blocked unless every claim in
   the output is `ok`.
4. **No source available**: render the section text as the literal
   string below (no fabricated fill-in):

   ```
   Data: not available — provide a source URL or accept "no data".
   ```

## Anti-patterns

- ❌ Paraphrasing the source ("the report says revenue grew by about
  twenty percent") — the validator's exact-match grep will reject this
  on the next iteration. Copy the verbatim sentence instead.
- ❌ Stitching multiple sentences together with `…` — the validator
  greps the full string, including the ellipsis. Either copy the
  original contiguous text, or split into two claims.
- ❌ Trimming source-side whitespace (e.g. `\n` between words) — the
  source's exact characters are what the validator sees.
- ❌ Omitting `published_at` when the page has it. The freshness gate
  protects downstream consumers from acting on stale numbers; skipping
  it short-circuits the gate.

## Triangulation note

For TAM/SAM/SOM and other core quantitative claims, SPEC-018 requires
≥2 independent-domain sources (two URLs on different parent domains).
With only one source, render the value as
`range: <low–high> [single-source]` rather than a point number. The
triangulation rule lives in the degraded-path skill template, not in
this validator — the validator's only job is per-claim quote +
freshness verification.
