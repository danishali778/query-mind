# AI Dashboard Generation

QueryMind can turn a natural-language objective into a private draft dashboard.

## Configuration

```text
DASHBOARD_AI_ENABLED=true
DASHBOARD_AI_MAX_WIDGETS=8
DASHBOARD_AI_DEFAULT_WIDGETS=6
DASHBOARD_AI_MAX_ACTIVE_PER_USER=1
DASHBOARD_AI_MAX_PROMPT_CHARS=2048
CELERY_DASHBOARDS_QUEUE=dashboards
DASHBOARD_RUN_EVENT_TTL_SECONDS=3600
DASHBOARD_RUN_EVENT_MAXLEN=500
DASHBOARD_RUN_HEARTBEAT_SECONDS=15
```

The interactive Celery worker must listen to both `interactive` and `dashboards`:

```text
celery -A app.workers.worker:app worker --loglevel=info --queues interactive,dashboards
```

Docker Compose `agent-worker` is configured for this queue pair.

## Workflow

1. `POST /api/dashboard/generations` starts planning (no SQL).
2. Client streams progress from `/events`.
3. User reviews/edits the plan, then `POST .../approve`.
4. Approval atomically creates an AI draft dashboard and placeholder widgets.
5. Workers generate widgets sequentially and replace placeholders.
6. Partial success keeps successful widgets; failed widgets can be retried/regenerated.

## Safety

- Planning never executes SQL.
- Widget generation uses the shared read-only analysis pipeline.
- AI dashboards start as private `draft` dashboards (`creation_mode=ai`).
- Dynamic shared filters are not auto-generated in V1.

## Operations

- Stale planning/execution runs are recovered by the `recover-stale-dashboard-runs` beat task.
- Terminal run states cannot reopen except via explicit retry/regenerate of items.
- Do not log prompts, generated SQL, row values, or schema samples at normal production levels.
