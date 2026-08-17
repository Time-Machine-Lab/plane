# OpenSpec Agent Guide

Before creating or editing an artifact, read `../docs/spec/README.md` and the module standards selected by its path mapping.

## Minimal artifacts

- Proposal: state the goal, scope, non-goals, affected modules, and applicable standards.
- Specs: describe observable requirements and scenarios, including important failure and authorization behavior.
- Design: document only decisions that need explanation, such as cross-module contracts, migrations, compatibility, rollout, or rollback.
- Tasks: keep the plan proportional to the change and end with development, one test deployment, and independent acceptance.

Do not copy command matrices or test levels into artifacts. The deployment entry point and acceptance process are defined by
`../docs/spec/test-environment.md` and `../docs/spec/testing-quality.md`.

After implementation, deploy once with `scripts/test/deploy-test.ps1`, then hand the change to an independent Tester.
The Tester reads the scenarios, uses the persistent test accounts and data, leaves product code unchanged, and writes
`changes/<change>/verification.md`. If verification fails, the implementation Agent fixes and redeploys; the same Tester
may retest the failed scenarios and necessary nearby regression. Do not complete or archive a change with a failing or
untested required scenario.
