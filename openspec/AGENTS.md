# OpenSpec Agent Guide

Before creating or editing an artifact, read `../docs/spec/README.md` and the module standards selected by its path mapping.

## Minimal artifacts

- Proposal: state the goal, scope, non-goals, affected modules, and applicable standards.
- Specs: describe observable requirements and scenarios, including important failure and authorization behavior.
- Design: document only decisions that need explanation, such as cross-module contracts, migrations, compatibility, rollout, or rollback.
- Tasks: keep the plan proportional and separate implementation, necessary development checks, and independent Tester verification. Add automated tests or runtime deployment only when the requirement and risk make them necessary.

Do not copy command matrices or test levels into artifacts. Do not require a new test harness for one isolated screen or make
the Tester rerun implementation checks. Validation selection, the optional deployment entry point, and acceptance are defined by
`../docs/spec/testing-quality.md` and `../docs/spec/test-environment.md`.

After implementation and necessary development checks, the primary Agent MUST create a new Tester sub-agent that did not
participate in implementation. The Tester independently reads the requirements, leaves product code unchanged, and uses the
least expensive sufficient method: static, offline, local, or test-environment validation. Deploy with
`scripts/test/deploy-test.ps1` only when the core goal requires a runtime environment, and deploy only affected services.
Do not require a fixed number of journeys or a `verification.md` unless OpenSpec, the user, or the change risk requires a
durable record. If validation fails, the implementation Agent fixes the issue and the same Tester rechecks only the failed
scope and necessary adjacent behavior. Use `blocked` only when the core goal cannot be validated because a required
prerequisite is unavailable. Do not complete or archive a change before independent Tester verification passes.
