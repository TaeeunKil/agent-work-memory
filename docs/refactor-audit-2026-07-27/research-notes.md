# Research Notes

## ActivityWatch

ActivityWatch uses small watchers that send timestamped events to a local
server. Its buckets are partitioned by watcher and host, so one collector does
not need to understand every other collector. This is useful prior art for
host/source identity and append-only intake, not for Work Almanac's knowledge
model.

- Architecture: https://docs.activitywatch.net/en/latest/architecture.html
- Data model: https://docs.activitywatch.net/en/latest/buckets-and-events.html

Borrow:

- collector/watchers terminate at a stable event contract;
- source and host identity are first-class;
- collection and analysis are separate;
- local-first storage is a real product choice.

Do not borrow:

- arbitrary untyped event payloads as the internal product contract;
- a raw activity dashboard as the primary user experience;
- localhost-only API security for a multi-host personal vault.

## OpenTelemetry Collector

The OpenTelemetry Collector separates receivers, processors, and exporters.
That vocabulary confirms the value of a deterministic intake pipeline whose
adapters do not decide product meaning.

- Collector: https://opentelemetry.io/docs/collector/
- Signals: https://opentelemetry.io/docs/concepts/signals/

Borrow the shape, not the machinery:

```text
collector adapter -> normalize/redact -> append ledger
```

Do not adopt OpenTelemetry schemas, deployment machinery, or a general
telemetry platform. Work Almanac events describe human work and provenance, not
distributed-service observability.

## Windows Task Scheduler

Windows Task Scheduler supports time- and event-based triggers and is the
native scheduler for the user's current machine.

- https://learn.microsoft.com/en-us/windows/win32/taskschd/task-scheduler-start-page

The existing `SchedulerAdapter` seam is sufficient. Add a Windows adapter
instead of leaking `schtasks` conditions into automation services.
