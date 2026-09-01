## Production Migration Hotfix Verification

- Result: PASS
- Test release: `20260901-202645-fa5697e27161`
- The Plane root and instance API returned HTTP 200; proxy, API, MCP, and PostgreSQL health checks passed.
- The persistent database recorded `db.0124`, `db.0125`, and `license.0007` exactly once, and both hierarchy indexes exist.
- Deployed migration inspection confirmed `Migration.atomic = False`, an atomic `RunPython` backfill, and a distinct project scan with model ordering cleared.
- A disposable copy of the persistent test database was rolled back to `db.0123` and migrated forward through `db.0124` and `db.0125` with exit code 0.
- The replay processed 3 projects and 55 active ProjectPage links exactly once, created 3 hierarchy state rows, and produced no cross-project parents.
- The disposable database was removed after verification and the persistent test data was not modified by the replay.

## Residual Risks

- A non-atomic schema migration can leave partial schema if an unrelated operation fails; production rollout still requires the existing pre-migration backup and migration-log observation.
- The current test data has no nested, archived, or invalid legacy relationships, so this focused verification covers the transaction boundary and project de-duplication rather than every hierarchy behavior in the full change.
