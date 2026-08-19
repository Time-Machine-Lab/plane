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
- Read `docs/spec/test-environment.md` before using the shared test environment or deploying a runtime change.
- More specific `AGENTS.md` files still apply inside their directory scope.

## OpenSpec workflow

- Use OpenSpec for product changes. Its artifact rules are defined in `openspec/config.yaml`.
- Keep artifacts proportional to the change. A design is needed only when architectural decisions, contracts, migrations, or rollout behavior require explanation.
- The default flow is: OpenSpec -> development and necessary checks -> verification by a new Tester sub-agent that did not participate in implementation -> completion or focused rework.
- The implementation Agent performs development checks but does not issue the final acceptance verdict. The primary Agent must create a fresh Tester sub-agent after implementation.
- Automated tests are added or run only when they provide clear regression value for the affected logic or risk boundary. Do not introduce a new test harness for one isolated screen.
- The Tester independently verifies only the requirement goal, directly affected behavior, and any necessary adjacent regression. There is no fixed journey count, and the Tester does not modify product code.
- Use static, offline, or local verification when sufficient. Only when the core goal requires a runtime environment should `scripts/test/deploy-test.ps1` deploy the affected services, without deploying or testing unrelated areas.
- A missing prerequisite is `blocked` only when it prevents validation of the core requirement. Skipping unrelated checks, unnecessary deployment, or an unauthorized third-party call is not blocked.
- If acceptance fails, the implementation Agent fixes the affected scope and the same Tester rechecks only the failure and necessary adjacent behavior.
- Create `openspec/changes/<change>/verification.md` only when OpenSpec, the user, or the change risk requires durable evidence. Do not complete or archive before independent Tester verification passes.
