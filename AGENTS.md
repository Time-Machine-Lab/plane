# Agent Development Guide

## Commands

- `pnpm dev` - Start all dev servers (web:3000, admin:3001)
- `pnpm build` - Build all packages and apps
- `pnpm check` - Run all checks (format, lint, types)
- `pnpm check:lint` - OxLint across all packages
- `pnpm check:types` - TypeScript type checking
- `pnpm fix` - Auto-fix format and lint issues
- `pnpm turbo run <command> --filter=<package>` - Target specific package/app
- `pnpm --filter=@plane/ui storybook` - Start Storybook on port 6006

## Code Style

- **Imports**: Use `workspace:*` for internal packages, `catalog:` for external deps
- **TypeScript**: Strict mode enabled, all files must be typed
- **Formatting**: oxfmt, run `pnpm fix:format`
- **Linting**: OxLint with shared `.oxlintrc.json` config
- **Naming**: camelCase for variables/functions, PascalCase for components/types
- **Error Handling**: Use try-catch with proper error types, log errors appropriately
- **State Management**: MobX stores in `packages/shared-state`, reactive patterns
- **Testing**: All features require unit tests, use existing test framework per package
- **Components**: Build in `@plane/ui` with Storybook for isolated development

## Backend tests (Docker)

The Django/pytest suite for `apps/api` runs in an isolated stack defined by `docker-compose-test.yml` at the repo root.

Prereq (once): `./setup.sh` — generates `apps/api/.env` from `.env.example`.

- Full suite: `docker compose -f docker-compose-test.yml up --build --abort-on-container-exit --exit-code-from api-tests`
- Subset: `docker compose -f docker-compose-test.yml run --rm api-tests pytest -m unit`
- Teardown: `docker compose -f docker-compose-test.yml down -v`

See `apps/api/tests/RUNNING_TESTS.md` for the full walkthrough and troubleshooting; see `apps/api/plane/tests/README.md` for test layout, conventions, markers, and fixtures.

## Module Development Standards

- Before planning or editing code, read `docs/spec/README.md`, `docs/spec/general-development.md`, and `docs/spec/testing-quality.md`.
- Use the path-to-standard mapping in `docs/spec/README.md` to load every applicable module guide.
- Read `docs/spec/module-structure.md` before adding or moving directories, packages, or runtime modules.
- Read `docs/spec/test-environment.md` before starting local apps, deploying a test build, or performing runtime acceptance.
- More specific `AGENTS.md` files still apply to files inside their directory scope.

## OpenSpec Development

- OpenSpec project context and per-artifact rules are defined in `openspec/config.yaml`.
- Every proposal must name affected modules and applicable `docs/spec` standards.
- Every design must describe changed cross-module contracts, migrations, rollout, and rollback where applicable.
- Every task list must include the L1-L4 test level and exact checks required by `docs/spec/testing-quality.md`.
- The implementation Agent must run L1 checks, then a newly created Tester sub-agent must independently execute final acceptance; code inspection alone is not evidence.
- The Tester receives minimal context, reads the change and test standards itself, must not modify product code, and writes `openspec/changes/<change>/verification.md`.
- If verification fails, the implementation Agent fixes the code and a different new Tester sub-agent performs the next verification cycle.
- Agent independence is a separation of responsibilities, not process, credential, or security isolation; all Agents share the worktree.
- Before accepting an OpenSpec change, link the Tester report from `tasks.md` and record pass/fail evidence for every mandatory scenario.
- Do not mark tasks or a change complete while any required local verification is failed, skipped, or unavailable.
