# OpenSpec Agent Guide

## Required standards

Before creating or editing an OpenSpec artifact, read `../docs/spec/README.md`. Use its path-to-standard
mapping to read every applicable module guide, plus `general-development.md` and `testing-quality.md`.

## Artifact requirements

- Proposal: identify affected modules, applicable standards, scope, non-goals, compatibility, risk and local acceptance method.
- Specs: describe observable requirements and GIVEN/WHEN/THEN scenarios, including failure and authorization paths.
- Design: document cross-module contracts, data/API/event changes, migration, test environment and observable acceptance evidence.
- Tasks: group work by module, include tests/docs, name exact local verification commands, and end with a Local acceptance record.

Do not invent a new module boundary when an existing `apps/*` or `packages/*` owner fits the change. When
implementation reveals a conflict with an artifact, update the artifact before continuing. Mark a task complete
only after both the code and its verification are complete. At the end of implementation, re-read proposal.md and
all delta specs, map every mandatory scenario to local evidence, and do not accept the change while any result is
failed or unverified.
