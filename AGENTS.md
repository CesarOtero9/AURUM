# AURUM Agent Operating Contract

## 1. Project Identity

AURUM is a fiscal-accounting intelligence platform centered on CFDI, SAT, SIF,
accounting reconciliation, provenance, inference, and auditability.

It is not merely:

- an XML reader;
- a SAT downloader;
- an Excel replacement; or
- a collection of automation scripts.

Its objective is to become the central traceable system connecting fiscal evidence
and accounting evidence. Do not turn this statement into product marketing.

## 2. Source of Truth and Context Loading

Follow this order:

1. Read `docs/PROJECT_STATE.md` first.
2. Read only specifications or documents directly relevant to the requested slice.
3. Search before opening large files.
4. Use targeted line ranges, search results, symbols, tests, and diffs when possible.

`PROJECT_STATE.md` is a navigation and state document. It does not replace accepted,
detailed specifications.

- Never automatically reread the entire documentation tree.
- Never reconstruct project history by reading every document.
- Do not read legacy code unless the task depends on it.
- Do not reread unchanged files repeatedly during the same task.
- If current user instructions conflict with stale documentation, stop and report the
  conflict rather than silently guessing.

## 3. Context Efficiency

- Keep tool output bounded; do not dump hundreds or thousands of irrelevant lines.
- Search before reading full files, and inspect only relevant failure tracebacks first.
- Summarize successful tests; retain relevant failure details.
- During iteration, run focused tests.
- Run the complete backend suite only at an explicit final validation gate or when a
  regression requires it.
- Do not repeat expensive commands that already passed unless relevant code changed.
- Do not repeatedly run `pip check`, `compileall`, full Ruff, or full pytest for small
  edits.
- Avoid generated files, caches, `.venv`, build artifacts, `.git`, large exports,
  Excel data, logs, and unrelated directories unless necessary.
- Never use token saving as a reason to omit a required correctness check.

## 4. Working Tree Safety

- Always inspect `git status --short` before modifying files.
- Preserve unrelated user changes.
- Do not reset, checkout, restore, clean, stash, amend, rebase, force-push, delete,
  or otherwise discard user changes unless explicitly instructed.
- Never commit or push without explicit authorization.
- Never stage unrelated files.
- Modify only files inside the requested increment.
- If Git reports dubious ownership, prefer a temporary per-command workaround such as
  `git -c safe.directory=C:/Users/USER/PycharmProjects/AURUM ...`.
- Do not change global Git configuration unless explicitly requested.
- Before proposing a final commit, report the exact files changed.

## 5. Increment Discipline

Work in small vertical increments:

1. Understand the accepted design.
2. Inspect only relevant implementation.
3. Implement only requested scope.
4. Add or update focused tests.
5. Run focused validation.
6. Run the final gate only when implementation is complete.
7. Report status.
8. Wait for explicit acceptance before commit or push.

Never opportunistically implement the next phase. Do not modify persistence for a
parser-only task, create endpoints for a domain-only task, or introduce frontend work
unless requested.

## 6. Architecture Guardrails

- Original XML and other evidence are immutable.
- Preserve original bytes exactly where the evidence contract requires it.
- The canonical fiscal identity is the SAT Timbre Fiscal Digital UUID.
- SAT state is dynamic and historical; do not derive it solely from stored XML.
- Distinguish source facts, observations, derived results, inferences, and human
  decisions.
- Derived data must retain provenance plus parser or rule version.
- Reprocessing must operate from immutable originals.
- Keep institution-specific values in catalogs or configuration, not generic domain
  logic.
- Keep business logic outside the UI.
- Treat legacy scripts and macros as functional knowledge and specification sources,
  not architectural templates.
- Risk and inference are separate concepts.
- Durable jobs and workers are separate from synchronous domain logic.
- `NETWORK_ERROR` must never be treated as `CFDI_NOT_FOUND`.

## 7. CFDI and SIF Core Semantics

The fiscal axis is `UUID`. The accounting/SIF axis is canonical `POLIZA`.
The primary trusted bridge is `Reporte XML SIF -> UUID <-> POLIZA`.

- CFDI-to-policy is many-to-many; never make one `cfdi.poliza_id` the global truth.
- Relationship state belongs to the relationship, not to the CFDI.
- A SIF-confirmed relationship must not be replaced by an inference.
- Preserve `ACTIVA` / `SIN EFECTO` history when supplied by the source.
- Preserve source and provenance for every confirmed relationship.

Use this conceptual evidence hierarchy:

1. Direct SIF XML report observation.
2. Human-confirmed relationship.
3. Strong deterministic rule.
4. Inference candidate.
5. Weak heuristic.

Never convert inference into official truth automatically.

## 8. Floating CFDI and Inference

A floating CFDI is a known CFDI without a trusted confirmed CFDI-to-policy
relationship. It does not automatically mean an invalid CFDI, an unaccounted
transaction, or an accounting error.

Inference produces candidates, not facts. Keep candidates distinguishable from
SIF-confirmed links, human-confirmed links, and rejected candidates. Inference must
remain explainable and auditable.

## 9. Persistence Principles

- PostgreSQL is the real persistence target.
- Enforce schema and data integrity through constraints and foreign keys where
  appropriate.
- Use `ON DELETE RESTRICT` for evidence/provenance chains unless an accepted design
  states otherwise.
- Do not silently overwrite historical or append-only facts.
- Make “current” views explicit projections over history, not replacements for it.
- Version parser and rule results.
- Normally correct derived data by creating a new parser or rule version rather than
  mutating historical derived facts.
- Avoid database ENUM when the accepted design prefers bounded strings or catalogs.
- Never use float for monetary or fiscal decimals.

## 10. Testing Strategy

During development, run targeted unit tests first and targeted integration tests where
applicable.

At an explicitly appropriate final gate, run relevant focused tests, the backend suite,
Ruff check, Ruff format check, `compileall`, `pip check`, and `git diff --check`.
Also run the PostgreSQL integration suite when persistence changed and the test database
is available.

If `AURUM_TEST_DATABASE_URL` is unavailable, report PostgreSQL validation as skipped or
not executed; never claim full persistence validation. Do not hide warnings that could
affect correctness. Known non-actionable dependency warnings may be summarized.

## 11. Documentation Discipline

- Update `PROJECT_STATE.md` only when an increment actually reaches its stated
  milestone.
- Do not mark implementation complete before tests pass.
- Do not casually rewrite accepted specifications during implementation.
- If implementation exposes a contradiction in an accepted specification, report it
  before changing architecture.
- Keep documentation changes minimal and factual.

## 12. Legacy Migration Rule

Treat scripts and macros being replaced as observable behavior and specification.

```text
legacy input -> capture behavior -> explicit specification -> new implementation
-> golden/compatibility tests
```

Do not blindly port quirks that conflict with accepted AURUM architecture, but never
silently discard business rules. This includes SAT download/validation scripts, CFDI
extractors, SIF Selenium automation, Reporte de Mayor VBA normalization, Reporte XML
SIF consolidation, MotorInferenciaCFDI, and Excel formulas or rules in operational
reports.

## 13. Output and Reporting Style

At the end of an implementation task, report concisely:

1. What changed.
2. Files changed.
3. Tests and validation executed.
4. Exact pass, fail, and skip counts.
5. Unresolved issues.
6. `git status --short`.
7. Whether commit or push occurred.

Do not provide long narrative summaries of unchanged architecture.

## 14. Stop Conditions

Stop and report rather than guessing when:

- accepted specifications materially conflict;
- a destructive Git action would be needed;
- required secrets or credentials are missing;
- required production access would be needed;
- a schema migration would contradict accepted data invariants; or
- the task unexpectedly requires unrelated architectural layers.

A missing PostgreSQL test URL is not a reason to rewrite code blindly; report the
unavailable integration validation.
