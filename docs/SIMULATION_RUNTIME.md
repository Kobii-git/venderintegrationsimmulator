# Simulation Runtime

Execution model for `0.3.0`.

## Lifecycle states

| Status | Meaning |
|--------|---------|
| `stopped` | Not generating events (default after create or stop) |
| `running` | Scheduler active; events generated per schedule |
| `completed` | Finite schedule reached `event_count` |
| `error` | Unhandled internal error during tick; scheduler job removed |

Pause is deferred to a later phase.

## Schedule types

| Type | Behaviour |
|------|-----------|
| `manual` | No scheduler. Use `POST /simulations/{id}/send` for one-shot delivery |
| `continuous` | Generate one event every `interval_seconds` until stopped |
| `finite` | Generate `event_count` events at `interval_seconds`, then auto-complete |

Finite targets apply to one start activation. Earlier manual sends, bursts, replays, and completed activations remain in lifetime counters and history but do not reduce the next finite run.

## Restart behaviour

**Default (safe):** When the application restarts, any simulation in `running` state is marked `stopped`. The `runtime_stats.interrupted_on_restart` flag is set to `true`. The operator must explicitly call `/start` again.

Set `SCHEDULER_RESUME_ON_RESTART=true` for safe opt-in resume. Startup pauses the scheduler, validates prior running records, restores eligible continuous/finite jobs and pull activations, marks invalid/manual/over-limit records `error`, then resumes. Continuous jobs wait one complete interval and do not catch up. Finite jobs continue from persisted progress; already complete jobs become `completed`.

## Multi-scenario selection

When `scenario_ids` contains multiple entries, events are generated using **round-robin** order. The current index is stored in `runtime_state.scenario_index` (internal; not exposed in API stats).

## Event variation

Each generated event receives:
- New `correlation_id` (UUID)
- Fresh `generated_at_iso` timestamp
- Product plugin dynamic fields (e.g. UpGuard `notification_id`, score drift)
- Optional `random_seed` controls pseudo-random scenario helpers and product-plugin values by constructing a local generator from `seed + event_sequence`.

The seed does not freeze real delivery time or identifiers: correlation IDs remain unique and actual attempt timestamps remain current. Replaying the same event sequence and configuration reproduces seeded values; changing sequence changes its deterministic stream. Plugins must use the injected generator and must not use module-global randomness.

## Pull datasets

Pull mode does not register outbound jobs and rejects `/send`. Start materializes `dataset_size` items per declared route from one activation anchor, with adjacent generated times separated by `item_interval_seconds`. Stop/start creates a new activation. Safe process resume keeps the prior activation and cursor identity.

## Safety limits (defaults)

| Setting | Default |
|---------|---------|
| `SCHEDULER_MIN_INTERVAL_SECONDS` | 1 |
| `SCHEDULER_MAX_INTERVAL_SECONDS` | 3600 |
| `SCHEDULER_MAX_EVENT_COUNT` | 10000 |
| `SCHEDULER_MAX_CONCURRENT_SIMULATIONS` | 10 |

## APIs

```text
POST /api/v1/simulations/{id}/start   # continuous or finite
POST /api/v1/simulations/{id}/stop
POST /api/v1/simulations/{id}/send    # manual one-shot (any schedule type)
GET  /api/v1/simulations/{id}         # includes runtime_stats
GET  /api/v1/simulations/{id}/events
GET  /api/v1/simulations/{id}/events/{event_id}
```

The preview UI sends the displayed payload with `preview_correlation_id` and `payload_edited`. An unchanged preview retains the displayed correlation ID and `generated` source; opting into raw JSON editing records `manual_override` metadata.

Product-level one-shot APIs (`/products/.../preview` and `/send`) remain available without persistence.

Manifest-defined workflow actions use
`POST /api/v1/simulations/{id}/actions/{action_id}`. An action applies its own delivery policy and
response assertion, then persists redacted attempts in event history with `event_kind=workflow_action`
and its `action_id`.
