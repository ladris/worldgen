<!-- Thanks for contributing! Keep PRs small and focused where possible. -->

## What & why
<!-- What does this change, and why? Link the issue/roadmap item if there is one. -->

Closes #

## Type of change
- [ ] Bug fix
- [ ] Feature
- [ ] Docs / tooling
- [ ] Refactor (no behaviour change)

## Contract impact
- [ ] **No** change to the Python↔Unreal contract.
- [ ] **Yes** — I updated **both** halves (Python `WorldGrid`/manifest *and*
      Unreal `FWorldGrid`/parsers) **and** bumped `schema_version` in
      `docs/CONTRACT.md`.

## Checklist
- [ ] Tests added/updated for any Python behaviour change (`tests_service/`).
- [ ] `python -m pytest tests_service/ -q` passes locally.
- [ ] Seam/persistence invariants preserved (no per-tile state, deterministic core).
- [ ] Docs updated where relevant (contract / roadmap / glossary / quickstart).
- [ ] For service changes: `python -m tools.contract_smoke` passes against a local run.

## Notes for reviewers
<!-- Trade-offs, follow-ups, anything you want eyes on. -->
