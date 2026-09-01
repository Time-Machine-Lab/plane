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
- Do not add or run automated tests by default. Add them only when the user explicitly requests them.

## Module standards

- Before planning or editing code, read `docs/spec/README.md` and the standards it maps to the affected paths.
- Read `docs/spec/module-structure.md` before adding or moving directories, packages, or runtime modules.
- Read `docs/spec/test-environment.md` before using the shared test environment or deploying a runtime change.
- More specific `AGENTS.md` files still apply inside their directory scope.

## OpenSpec workflow

- Use OpenSpec for product changes. Its artifact rules are defined in `openspec/config.yaml`.
- Keep artifacts proportional to the change. A design is needed only when architectural decisions, contracts, migrations, or rollout behavior require explanation.
- The default runtime-change flow is: OpenSpec -> implementation -> deploy affected services with `scripts/test/deploy-test.ps1` -> verification in the test environment by a fresh Tester sub-agent -> completion or focused rework.
- Local development checks are optional debugging aids, not a required phase or a prerequisite for deployment. Do not stop because the current host lacks Django, pytest, Ruff, Docker, or another test dependency.
- Do not add or run automated test suites, pytest, Ruff, local Docker tests, or a fixed lint/type/build matrix unless the user explicitly requests that exact evidence.
- After runtime implementation is complete, the primary Agent immediately deploys the affected services and creates a fresh Tester sub-agent that did not participate in implementation. The implementation Agent does not issue the final acceptance verdict.
- The Tester independently verifies the requirement goal, directly affected behavior, and any necessary adjacent regression against the deployed test environment. There is no fixed journey count, and the Tester does not modify product code.
- Pure documentation, static configuration, or other changes with no runtime behavior may use static or offline verification without deployment.
- A missing prerequisite is `blocked` only when it prevents validation of the core requirement. Skipping unrelated checks, unnecessary deployment, or an unauthorized third-party call is not blocked.
- If acceptance fails, the implementation Agent fixes the affected scope and the same Tester rechecks only the failure and necessary adjacent behavior.
- Create `openspec/changes/<change>/verification.md` only when OpenSpec, the user, or the change risk requires durable evidence. Do not complete or archive before independent Tester verification passes.
