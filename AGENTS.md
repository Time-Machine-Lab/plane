# Agent Development Guide

## Repository commands

- `pnpm dev` - start the web and admin development servers.
- `pnpm build` - build the monorepo when a release or dependency change requires it.
- `pnpm check` - run all repository checks when explicitly required.
- `pnpm check:lint` - run OxLint.
- `pnpm check:types` - run TypeScript type checking.
- `pnpm turbo run test --affected` - run existing tests for affected JavaScript packages.
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
- The default runtime flow is: OpenSpec -> development -> affected CI checks/tests -> one `scripts/test/deploy-test.ps1` deployment -> independent Tester acceptance.
- Evidence has one owner: pre-commit owns staged formatting/lint, CI owns affected static checks and automated tests, the deploy script owns migration/startup/health, and the Tester owns user-visible workflows.
- Keep automated coverage focused on logic and risk boundaries such as authorization, secrets, data isolation, migrations, serialization, and event behavior. Do not introduce a new test harness for one isolated screen.
- The Tester groups required scenarios into 3-7 minimal user journeys, uses persistent test accounts and data, and does not rerun CI commands or inspect normal-success logs.
- A missing credential, account, observer, or usable environment is `blocked`, not a product failure. `fail` means the deployed product behaved incorrectly.
- If acceptance fails, the implementation Agent fixes and redeploys; the same Tester retests the failed journey and one necessary nearby regression instead of repeating the full acceptance set.
- Documentation-only and static-only changes do not require runtime deployment. Record concise `pass`/`fail`/`blocked` evidence in `openspec/changes/<change>/verification.md`; do not complete or archive while a required journey is failing or blocked.
