When implementing a new backend feature:
1. Ask orchestrator to classify the task.
2. Ask fastapi-service-architect to define service boundaries and integration points.
3. Ask the relevant specialist to design the feature logic.
4. Ask route-contract-guardian if the feature changes request/response behavior.
5. Ask async-job-queue-specialist only if the feature explicitly touches long-running jobs, cancellation, or progress.
6. Ask config-observability-guardian if the feature adds settings, providers, logging, or temp-file behavior.
7. Produce:
   - architecture summary
   - implementation plan
   - code changes
   - test cases

Always attach `../project-rules.md` to every specialist step.
