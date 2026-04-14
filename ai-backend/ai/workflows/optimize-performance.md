When optimizing backend performance:
1. Ask orchestrator to classify the bottleneck.
2. Ask the stage owner to identify the highest-cost path:
   - provider calls -> provider-abstraction-engineer
   - caption/image work -> vision-caption-pipeline
   - script generation/parsing -> script-generation-orchestrator
   - queue throughput/cancellation -> async-job-queue-specialist
3. Ask fastapi-service-architect to verify that the optimization does not break service boundaries.
4. Ask config-observability-guardian if new metrics, logs, or settings are needed to validate the change.
5. Produce:
   - bottleneck summary
   - optimization plan
   - code changes
   - measurement and regression tests

Always attach `../project-rules.md` to every specialist step.
