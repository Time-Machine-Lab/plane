# OpenSpec Agent Guide

Before creating or editing an artifact, read `../docs/spec/README.md` and the module standards selected by its path mapping.

## Minimal artifacts

- Proposal: state the goal, scope, non-goals, affected modules, and applicable standards.
- Specs: describe observable requirements and scenarios, including important failure and authorization behavior.
- Design: document only decisions that need explanation, such as cross-module contracts, migrations, compatibility, rollout, or rollback.
- Tasks: keep the plan proportional and separate implementation, automated verification, one runtime deployment, and independent acceptance.

Do not copy command matrices or test levels into artifacts. Do not require a new test harness for one isolated screen or make
the Tester rerun CI checks. The evidence owners, deployment entry point, and acceptance process are defined by
`../docs/spec/testing-quality.md` and `../docs/spec/test-environment.md`.

After affected CI checks and tests pass, deploy runtime changes once with `scripts/test/deploy-test.ps1`, then hand the change
to an independent Tester. The Tester groups required scenarios into 3-7 minimal user journeys, uses persistent test accounts
and data, leaves product code unchanged, and writes `changes/<change>/verification.md`. If verification fails, the
implementation Agent fixes and redeploys; the same Tester retests the failed journey and one necessary nearby regression.
Use `blocked` for missing environment prerequisites and `fail` only for incorrect product behavior. Do not complete or
archive a change with a failing, blocked, or untested required journey.
