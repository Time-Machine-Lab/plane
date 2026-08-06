# OpenSpec Agent Guide

## Required standards

Before creating or editing an OpenSpec artifact, read `../docs/spec/README.md`. Use its path-to-standard
mapping to read every applicable module guide, plus `general-development.md` and `testing-quality.md`.
Read `test-environment.md` before starting a local app, deploying to the test server, or running acceptance.

## Artifact requirements

- Proposal: identify affected modules, applicable standards, scope, non-goals, compatibility, risk, required L1-L4 level and acceptance environment.
- Specs: describe observable requirements and GIVEN/WHEN/THEN scenarios, including failure and authorization paths.
- Design: document cross-module contracts, data/API/event changes, migration, test environment and observable acceptance evidence.
- Tasks: group work by module, include tests/docs, name exact verification commands, and end with an acceptance record linked to `verification.md`.

Do not invent a new module boundary when an existing `apps/*` or `packages/*` owner fits the change. When
implementation reveals a conflict with an artifact, update the artifact before continuing. Mark a task complete
only after its code and stated L1 checks are complete; final change acceptance additionally requires the independent
Tester report below.

After implementation and L1 checks, create a new Tester sub-agent with only the change path and applicable test
standards. The Tester must independently read the artifacts, select and execute L1-L4 verification using
`../docs/spec/test-environment.md`, must not modify product code, and must write
`changes/<change>/verification.md`. This is responsibility independence, not security isolation: Agents share the
worktree and credentials available to the process. If a test fails, return it to the implementation Agent; after a
fix, create a different new Tester for the next verification cycle. Link the final report from `tasks.md` and do not
accept the change while any mandatory result is failed or unverified.
