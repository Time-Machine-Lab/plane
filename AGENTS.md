# Agent Development Guide

## Repository commands

- `pnpm dev` - start the web and admin development servers.
- `pnpm build` - build the monorepo when a release or dependency change requires it.
- `pnpm check` - run all repository checks when explicitly required.
- `pnpm check:lint` - run OxLint.
- `pnpm check:types` - run TypeScript type checking.
- `pnpm fix` - apply repository formatting and lint fixes.
- `pnpm turbo run <command> --filter=<package>` - run a command for an affected package or app.
- `pnpm --filter=@plane/ui storybook` - start Storybook on port 6006.

## Code style

- Use `workspace:*` for internal dependencies and `catalog:` for external dependencies.
- Keep TypeScript strict and fully typed.
- Follow the existing naming, error-handling, MobX, component, and test patterns in the affected module.
- Put shared components in `@plane/ui` when they are genuinely reusable.
- Add focused automated tests when they provide useful regression coverage; do not turn every change into a full-repository test run.

## Module standards

- Before planning or editing code, read `docs/spec/README.md` and the standards it maps to the affected paths.
- Read `docs/spec/module-structure.md` before adding or moving directories, packages, or runtime modules.
- Read `docs/spec/test-environment.md` before deploying or testing a runtime change.
- More specific `AGENTS.md` files still apply inside their directory scope.

## OpenSpec workflow

- Use OpenSpec for product changes. Its artifact rules are defined in `openspec/config.yaml`.
- Keep artifacts proportional to the change. A design is needed only when architectural decisions, contracts, migrations, or rollout behavior require explanation.
- The default implementation flow is: OpenSpec -> development -> one `scripts/test/deploy-test.ps1` deployment -> independent Tester acceptance.
- The deploy script owns environment preparation and its internal checks. Do not duplicate full builds, local Docker suites, or the same checks in multiple workflow stages.
- The Tester reads the change scenarios, uses the persistent test accounts and data, and verifies only the affected behavior plus basic availability. The Tester does not modify product code.
- If acceptance fails, the implementation Agent fixes and redeploys; the same Tester may retest the failed scenarios and necessary nearby regression.
- Record concise pass/fail evidence in `openspec/changes/<change>/verification.md`. Do not complete or archive a change while a required scenario is failing or cannot be tested.
