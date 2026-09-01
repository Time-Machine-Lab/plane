# OpenSpec Agent Guide

Before creating or editing an artifact, read `../docs/spec/README.md` and the module standards selected by its path mapping.

## Minimal artifacts

- Proposal: state the goal, scope, non-goals, affected modules, and applicable standards.
- Specs: describe observable requirements and scenarios, including important failure and authorization behavior.
- Design: document only decisions that need explanation, such as cross-module contracts, migrations, compatibility, rollout, or rollback.
- Tasks: for runtime changes, separate implementation, immediate test-environment deployment, and independent Tester acceptance. Do not add a development-check phase or automated-test tasks unless the user explicitly requests them.

Do not copy command matrices or test levels into artifacts. Do not require a new test harness for one isolated screen or make
the Tester rerun implementation checks. Deployment and acceptance are defined by
`../docs/spec/testing-quality.md` and `../docs/spec/test-environment.md`.

After runtime implementation, the primary Agent MUST immediately deploy affected services with
`scripts/test/deploy-test.ps1`, then create a new Tester sub-agent that did not participate in implementation. The Tester
independently reads the requirements, leaves product code unchanged, and validates observable behavior in the deployed test
environment. Local checks are optional debugging aids and are never deployment prerequisites. Missing host-side Django,
pytest, Ruff, Docker, or similar tooling is not a blocker. Automated tests and fixed lint/type/build matrices are included
only when the user explicitly requests them. Pure documentation or static configuration changes may use static or offline validation.
Do not require a fixed number of journeys or a `verification.md` unless OpenSpec, the user, or the change risk requires a
durable record. If validation fails, the implementation Agent fixes the issue and the same Tester rechecks only the failed
scope and necessary adjacent behavior. Use `blocked` only when the core goal cannot be validated because a required
prerequisite is unavailable. Do not complete or archive a change before independent Tester verification passes.
