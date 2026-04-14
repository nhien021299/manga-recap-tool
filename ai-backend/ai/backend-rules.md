# Backend Runtime Rules

## Service Design
- Keep route handlers focused on validation, dependency access, and HTTP response mapping.
- Put orchestration logic in services, not in route modules.
- Keep provider clients narrow and replaceable.
- Prefer one clear responsibility per service class.

## API Rules
- Preserve stable request and response contracts.
- Validate inputs early and fail with actionable errors.
- Keep async endpoints non-blocking where possible.
- Expose progress and job state in a predictable way.

## Pipeline Rules
- Treat caption understanding and script generation as separate stages.
- Cache only when cache keys include the full provider-sensitive inputs.
- Raw provider output is diagnostic data, not trusted domain data.
- Convert provider responses into domain models before downstream use.

## Queue Rules
- Queue state transitions must be explicit and auditable.
- Cancellation checks must exist before and after expensive stages.
- Cleanup must run in `finally` paths.
- Avoid hidden background work that is not tracked by the queue.

## Config and Observability
- All provider URLs, model names, and feature toggles belong in settings.
- Log stage starts, completions, retries, and provider failures.
- Keep logs useful for debugging production issues without dumping unnecessary noise.
- Temp directories and transient artifacts must stay isolated per job.

## Testing Rules
- Test route contracts, queue transitions, and failure handling.
- Cover cancellation, cleanup, and provider error paths.
- Prefer service-level tests for pipeline logic and route tests for HTTP behavior.
- Add regression tests when fixing bugs in job lifecycle or schema mapping.

## Avoid
- provider logic inside route files
- route handlers that assemble large domain objects directly
- hidden mutation across services
- silently swallowing provider parse failures
- partial cleanup paths
- schema drift between models and returned payloads
