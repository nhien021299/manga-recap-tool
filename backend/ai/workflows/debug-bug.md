When debugging a backend bug:
1. Ask orchestrator to classify the failing area.
2. Ask python-backend-refactor-reviewer to identify the most likely failure mode and missing coverage.
3. Ask the relevant specialist to trace the bug in its domain:
   - routes/contracts -> route-contract-guardian
   - providers -> provider-abstraction-engineer
   - caption stage -> vision-caption-pipeline
   - script stage -> script-generation-orchestrator
   - queue/cancellation -> async-job-queue-specialist only for explicitly queue-based paths
   - config/logging/temp files -> config-observability-guardian
4. Produce:
   - root-cause summary
   - minimal fix
   - regression tests
   - operational risk notes

Always attach `../project-rules.md` to every specialist step.
