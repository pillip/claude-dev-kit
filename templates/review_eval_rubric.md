# Review Eval Rubric (ISSUE-002)

> The judge (`scripts/eval_review.py` via `claude -p`) scores a `review_notes.md`
> against the PR diff on the four dimensions below. Versioned here so the rubric
> can be tuned without touching code. Edit the dimensions/weights freely; the
> loader tolerates extra prose and only requires the four `### <dimension>`
> headers to be present.

The judge reads the **PR diff** independently and the **review notes**, then
scores how well the notes covered what the diff actually warranted. It is NOT
re-reviewing the code for the user — it is auditing the review.

## Output contract

Return a single JSON object (no prose around it):

```json
{
  "scores": {
    "coverage": 0-5,
    "false_positive_rate": 0-5,
    "actionability": 0-5,
    "traceability": 0-5
  },
  "verdict": "pass" | "concerns",
  "missed_findings": [
    {
      "severity": "Critical" | "High" | "Medium" | "Low",
      "title": "what the review missed",
      "diff_ref": "path:line-range",
      "rubric": "coverage",
      "evidence": "why the diff warranted a finding here"
    }
  ],
  "concerns": [
    { "rubric": "false_positive_rate", "diff_ref": "path:line", "note": "..." }
  ]
}
```

`verdict` is `concerns` if any Critical/High finding was missed OR any dimension
scores ≤ 2; otherwise `pass`. Every entry in `missed_findings` / `concerns` MUST
carry a `diff_ref` (a real path + line range from the diff) and a `rubric` tag —
no free-floating opinions.

## Dimensions

### coverage
Did the review flag every Critical/High issue the diff actually contains?
Missing a real high-impact bug is the most serious failure. Score 5 = no
material miss; 0 = missed an exploitable/data-loss issue present in the diff.

### false_positive_rate
Are the review's findings real, or does it flag non-issues (already-validated
input, middleware-checked permissions, style nits dressed as bugs)? Score 5 =
every finding is a real issue; 0 = majority are false positives.

### actionability
Does each finding say what is wrong, why it matters, and a concrete fix — usable
by a developer without a follow-up question? Score 5 = all actionable; 0 = vague
"consider improving this" with no fix.

### traceability
Does each finding cite the specific diff line(s) it refers to, so a reviewer can
verify it against the change? Score 5 = every finding traces to a diff location;
0 = findings float without references.
