# PWM persistence and Hydraulic Consistency

[English](#english) · [Deutsch](#deutsch)

## English

### Scope

This change optimizes the existing scheduler and adds instrumentation. Both
strategies, heat entitlements, one ordinary start per logical period, genuine
priority response, minimum times, deferral limits and conservative restart
accounting remain authoritative. Hydraulic Consistency is a competition proxy,
not a scheduling objective or a measurement of water flow or delivered energy.

### Persistence audit and write policy

The original implementation checkpoints after every reconcile, before commands,
after their confirmation and at orderly shutdown. Every checkpoint serializes
the entire learning Store, including unrelated PID histories. Its wall-clock
sample timestamps also change during otherwise idle operation.

| Trigger | New policy |
| --- | --- |
| Before actuator command / ON intent | Await a critical durable checkpoint; never debounce. |
| After actuator confirmation | Await a critical checkpoint, including consumed ordinary allowance and accumulator credit. |
| Restart safety-OFF reconciliation | Preserve both awaited barriers. |
| Active elapsed delivery / changed open entitlement | Save meaningful accounting changes; do not extend the previous uncertainty interval with a new periodic delay. |
| Unchanged idle reconcile | Skip timestamps, projections and diagnostic-only changes. |
| PID revision after a closed ordinary pulse | Preserve the live accounting, but skip reconstructible closed-allocation revisions when no other safety state changed. |
| Orderly shutdown | Force an awaited final checkpoint. |
| Multiple groups / concurrent requests | One journal write lock, immutable payload copies and no delayed PWM writes. |

The signature is semantic: idle sample time and reconstructible diagnostic
counters do not make state dirty. Active consumed time, pending intent, signed
credit, minimum-time edges, priority/deadlines and ordinary allowances do.
Already closed revision counters may revert to their last durable value on an
unexpected restart; they cannot grant another pulse. No positive credit is
invented and the signed conservation identity is maintained. Do not interpret
requested/cancelled cumulative revisions as measured delivered heat.

The new Store key is `adaptive_climate_pwm_coordination`, version 1. PWM writes
contain group journals only. Learning histories and existing storage versions
are retained. Migration uses two phases:

1. Atomically save the dedicated journal from the legacy payload.
2. Await a durable migration marker in the learning Store before allowing ON.

Legacy journals are retained. Once marked, a missing/corrupt dedicated file
blocks coordinated ON rather than restoring stale legacy entitlements. A crash
between the two phases safely retries migration. Marker writes use the same
learning Store/lock as delayed learning saves, preventing a stale learning write
from removing the marker. All physical file access goes through HA Store APIs.

HA 2026.11 `Store.async_save()` logs certain serialization/write errors without
raising them. A narrow Store subclass acknowledges completion of its
`_async_write_data` hook; returning without acknowledgement is a failed barrier.
This also rejects deferred shutdown saves. Atomic replacement is explicitly
enabled. Executor-backed writes are shielded and drained before cancellation
releases the journal lock, so an older replacement cannot land after a newer
checkpoint. The private acknowledgement hook is a compatibility boundary,
covered by the real-HA probe in CI; unsupported implementations fail closed.

References: [HA Store implementation](https://github.com/home-assistant/core/blob/2026.11.0/homeassistant/helpers/storage.py),
[HA file helpers](https://github.com/home-assistant/core/blob/2026.11.0/homeassistant/util/file.py).
Atomic replacement is not a promise about storage-controller caches, hardware
power-loss protection or fsync of every directory entry.

### CPU work

The immutable highest-weight member is cached. Identical cyclic planner inputs
reuse the existing deterministic plan. An unchanged timer deadline and effective
request state can reuse the existing timer; unique callback tokens still reject
cancelled/queued callbacks. All time-dependent accounting, boundaries, priorities,
minimum times, external observations and executable repair still run. No
reconcile is skipped just because its initiating zone has unchanged PID output.

### Hydraulic Consistency definition

For configured zone weight `w_i`, total active weight `W`, and an active zone:

`R_i = (W - w_i) / W`

Existing `hydraulic_weight` is used live. Supply comparable nominal zone flows
as weights when known, otherwise circuit counts, otherwise 1. Do not mix
incompatible units or unrelated pumps in a group. The offline mapping accepts
`nominal_flow`, then `heating_circuits`, then `weight` (default 1).

Exact transition intervals accumulate `T`, `S1 = sum(R*dt)` and
`S2 = sum(R²*dt)`. The score is:

`HC = clamp(100 * (1 - 2 * sqrt(max(0, S2/T - (S1/T)²))), 0, 100)`

Intra-pulse variation is the square root of the duration-weighted within-pulse
variance. Inter-pulse variation is the duration-weighted standard deviation of
pulse means, including valid observed fragments; boundary fragments are flagged.
Competing-load changes count changes within active pulses, not their start/end.
Aggregate weighted overlap is `integral sum(i<j) w_i*w_j*ON_i*ON_j dt`.
It has units of relative weight squared times seconds, not litres or energy.

A score needs at least **60 valid active seconds and one complete valid pulse**,
or **900 valid active seconds** for long continuous/boundary-censored heating.
Inter-pulse variation remains unavailable until two valid observed pulse fragments
exist; one long pulse can establish constant competition, not inter-pulse repeatability.
Otherwise `score: null` / `status: insufficient_data` is returned. Constant solo
operation and constant overlap can both score 100; always inspect solo percent,
mean competition, variation, load changes, pulse count and coverage together.
For weights 4 and 1, alternating equally between solo and overlap gives the
large zone mean competition 0.1, standard deviation 0.1 and score 80. The small
zone, if always overlapping, can score 100 despite having zero solo time.

The live `pwm_coordination.hydraulic_consistency` object uses a rolling 24-hour
window, transition-only bounded memory (20,000 events maximum), and minute-cached
diagnostics invalidated by real state changes. No extra timer, Store write or
explicit HA state-write call is added. Missing outputs/fallback intervals are
unknown, not OFF. Collection resets on restart; no perfect initial score is
reported. Cumulative active/solo/R/R² time integrals and a `collection_id` also
allow external aggregation across non-overlapping observations. Truncation of
the event cap shortens reported coverage; cumulative counters remain in memory.

Thermal actuators may take minutes to move. HA output/helper states are not
confirmed valve positions, physical pump feedback, differential pressure,
actual flow, supply/return temperatures or heat measurements. More repeatable
competition may benefit learning, but this diagnostic does not establish a
causal improvement in PID tuning or room comfort.

### Historical CSV analysis

Run from a checkout using Python 3.11+; Home Assistant is not required:

```sh
python tools/analyze_hydraulic_consistency.py \
  --dataset baseline=exports/independent \
  --dataset coordinated=exports/coordinated \
  --mapping examples/pwm-hydraulic-mapping.json \
  --start 2026-10-24T00:00:00+02:00 --end 2026-11-01T00:00:00+01:00 \
  --timezone Europe/Vienna --rolling 24h,7d \
  --minimum-pulse-seconds 1 --output analysis
```

Add `--html` for an optional static report with tables and an output-state
interval timeline. This report runs entirely offline. On platforms without a
system timezone database, install Python's `tzdata` package.

The mapping can set independent windows without separate invocations:

```json
{"datasets": {
  "baseline": {"start": "2026-10-24T00:00:00+02:00", "end": "2026-10-25T00:00:00+02:00"},
  "coordinated": {"start": "2026-10-25T00:00:00+02:00", "end": "2026-10-26T00:00:00+01:00"}
}}
```

`--start`/`--end` override these windows. Optional `initial_states` maps input
entity IDs to `on`/`off` seeds before the event stream; earlier CSV events advance
these seeds before the analysis start. Put a timed initial snapshot in the CSV
when its timestamp matters.

The sample dates illustrate DST handling, not a claim about installed versions.
For datasets covering different dates, run each with its actual window and use
explicit labels; do not force common timestamps onto unrelated periods. `--input`
is repeatable and accepts a CSV or directory; `--label` names a single dataset.
Mapping files use JSON, with configurable group/zone aliases and display names.
CSV columns are `entity_id,state,last_changed` (or `last_updated`/`timestamp`).
Timestamps must contain `Z` or an explicit offset. Internal arithmetic uses UTC;
calendar days use the chosen timezone. A Vienna DST-end day is 25 hours, while
rolling 24h/7d windows are exactly 86,400/604,800 elapsed seconds.

Out-of-order rows and identical duplicates are supported. Conflicting states for
one entity at an identical timestamp become unknown with a warning. Simultaneous
transitions across different zones are applied atomically; a handover cannot
manufacture an OFF/ON edge. Short pulses remain in raw totals and pulse output,
with a reporting flag rather than silent removal. Edge pulses are censored.

No state is assumed OFF before its first known event. Unavailable/unknown data
invalidates affected hydraulic intervals; logical OR can still prove pump ON
when another known zone is ON. Long unchanged states are carried forward, not
automatically called missing. Export continuity must be verified externally or
its warning retained. Optional `coverage` intervals require an actual known
initial event at their start; `maintenance_exclusions`/`--exclusions` explicitly
remove known outages. Hidden downtime cannot be reconstructed from event CSVs.

Outputs: the five requested daily/per-zone/pulse/comparison CSVs and `summary.json`,
plus `pump_starts_rolling.csv` and `hydraulic_consistency_rolling.csv`.
Rolling maxima include their actual comparison windows. ON/OFF duration averages
use only complete spells, not censored boundaries. Whole-period daily/weekly
start rates are normalized by known pump-state time and are not full-calendar
counts. Daily CSV rows retain actual elapsed time and coverage.

Version labels are explicit. Observational comparisons may differ in heat demand,
temperature, setpoints, occupancy, coverage and durations; they do not establish
scheduler causality. Same-demand controlled replays provide stronger evidence.
Without a supplied independent dataset, no historical baseline benefit is
invented; the comparison file remains empty with an explanatory status file.

### HA, Recorder, InfluxDB and charts

See [Template sensor examples](../examples/pwm-hydraulic-sensors.yaml) and
[ApexCharts examples](../examples/pwm-hydraulic-apexcharts.yaml). They are optional
configuration examples using synthetic entity IDs; no helpers are installed by
this change. Replace IDs/names and keep unavailable data unavailable.
HC/solo/control output use percent, competition is dimensionless, and the rolling
load-change count is a measurement rather than a lifetime increasing counter.

An existing InfluxDB setup that collects the sensor domain can collect these
Template sensors; explicit include filters may need the new IDs. Recorder can
record them too. Neither uses the critical PWM journal. Chart `last` grouping
shows score snapshots; a 7-day chart does not convert 24-hour snapshots into a
7-day consistency score.

For a true longer-period score, aggregate **non-overlapping increments** of
cumulative active time, `R*dt` and `R²*dt`, partitioned by `collection_id` so a
restart does not become a negative increment. Recompute mean, variance and HC
from the summed moments, with adequate pulse/coverage checks. Never sum
overlapping rolling-24h totals or average daily HC scores. The offline 7-day
rows calculate the exact metric directly from event intervals.

### Validation and deployment

The benchmark starts from commit `e2501cb`, uses four synthetic weighted zones,
12 deterministic 24h traces (both strategies, 60s/10s ticks, idle, steady,
PID noise, full demand and priorities), counts completed serialized payload
writes and compares every transition and signed ledger. Payload bytes are
compact JSON bytes, not measured flash write amplification. Wall-clock replay
time is a host measurement, not a Raspberry Pi performance claim.

Run opt-in benchmarks with `PWM_BENCHMARK_OUTPUT=<directory>` and
`pytest tests/test_pwm_persistence_benchmark.py`. Existing normal regressions
remain enabled. `tools/verify_pwm_store.py` runs outside pytest's HA mocks
against real HA, exercising atomic writes, serialization failure, injected
ENOSPC, a real permission failure, cancellation and deferred shutdown saves.
Injected ENOSPC is not a physical full-flash-device experiment.

Back up configuration and learning storage before upgrade. Restart HA after
installing, verify active groups, successful migration and existing balances.
Diagnostic collection starts fresh; wait for valid heating pulses. A missing
dedicated journal after migration deliberately blocks ON; do not remove the
marker to bypass protection. For rollback to older code, first stop participating
zones safely and retain both stores/backups: older code cannot read the new
journal and its retained legacy journal is stale. Do not hot-swap old code into
an active group or reset learned PID data as a migration workaround.

## Deutsch

### Umfang und Speicherstrategie

Diese Änderung optimiert die bestehende Planung und ergänzt Diagnosen. Beide
Strategien, Wärmebudgets, ein normaler Start pro logischer Periode, sofortige
zulässige Prioritätsreaktion, Mindestzeiten, Aufschubgrenzen und konservative
Neustartabrechnung bleiben erhalten. Der hydraulische Score wird nicht zum
neuen Planungsziel.

Bislang schreibt jeder Abgleich den gesamten Lernspeicher einschließlich
PID-Historien. Künftig enthält `adaptive_climate_pwm_coordination` nur die
PWM-Journale. Vor Befehlen und nach Bestätigung sowie beim geordneten Stoppen
wird weiterhin gewartet. Änderungen laufender Lieferzeit und offener Budgets
werden nicht durch längere periodische Wartezeiten verwässert. Unveränderte
Leerlauf-Zeitstempel, Prognosen und rein diagnostische Änderungen lösen keine
neue Speicherung aus. Geschlossene PID-Revisionen bleiben live sichtbar;
nach unerwartetem Neustart können diese rekonstruierbaren Zähler auf ihren
letzten dauerhaften Stand zurückfallen, ohne einen neuen Impuls freizugeben.

Die Migration schreibt zuerst den neuen Store und danach einen dauerhaften
Marker im Lernspeicher. Erst dann darf die Gruppe EIN ausführen. Alte Daten
bleiben erhalten. Nach erfolgter Migration wird eine fehlende/beschädigte neue
Datei nicht durch das veraltete Legacy-Journal ersetzt. Marker und verzögerte
Lernspeicherungen verwenden dieselbe Store-Instanz und deren Schreib-Lock.

HA protokolliert manche Store-Fehler ohne Exception. Deshalb bestätigt eine
schmale Unterklasse den tatsächlich abgeschlossenen Schreibpfad; eine bloße
Rückkehr aus `async_save` genügt nicht. Atomarer Dateiaustausch ist aktiviert.
Bei Abbruch wird laufende Executor-Dateiarbeit abgewartet, bevor das Lock
freigegeben wird. Der private Bestätigungshook ist eine ausdrücklich geprüfte
Kompatibilitätsgrenze. Atomarer Austausch garantiert keine Absicherung gegen
alle Hardware-/Stromausfallarten.

Unveränderte reine Phasenpläne, konstante Gewichte und passende Ereignistimer
werden wiederverwendet. Veraltete Callbacks bleiben entwertet. Zeitabhängige
Abrechnung, Grenzen, Prioritäten und Ausgangsänderungen werden weiterhin geprüft.

### Hydraulische Konsistenz

Für jede aktive Zone wird `R = (aktive Gesamtgewichtung - Eigengewicht) /
aktive Gesamtgewichtung` berechnet. Vorhandene `hydraulic_weight`-Werte können
vergleichbare Nenndurchflüsse, sonst Kreiszahlen, sonst 1 darstellen. Das
Offline-Mapping bevorzugt expliziten Nenndurchfluss, dann Kreiszahlen, dann
relatives Gewicht. Hydraulisch unabhängige Gruppen getrennt halten.

Die englische Formel oben definiert den Score und die gewichteten Momente
vollständig. Ein Score benötigt mindestens 60 gültige aktive Sekunden und einen
vollständigen gültigen Impuls oder 900 gültige aktive Sekunden bei langem
Dauerbetrieb beziehungsweise Randimpulsen. Die Variation zwischen Impulsen bleibt
bis zu zwei gültigen beobachteten Impulsfragmenten nicht verfügbar. Ein einzelner
langer Impuls belegt konstante Konkurrenz, keine Wiederholbarkeit zwischen Impulsen.
Unterhalb dieser Grenzen ist der Score nicht verfügbar. Konstante Überlappung
kann ebenso 100 ergeben wie konstanter Alleinlauf. Deshalb immer Alleinlauf,
mittlere Konkurrenzlast, Variation innerhalb/zwischen Impulsen, Lastwechsel,
Abdeckung und Impulszahl zusammen betrachten. Gewichtete Überlappung ist die
Summe der paarweisen Gewichtsprodukte über die gemeinsame EIN-Zeit.

Live wird ein rollendes 24-Stunden-Fenster mit begrenztem Ereignisspeicher
ausgewertet. Diagnosen werden minutenweise zwischengespeichert und bei
Zustandswechseln erneuert. Es entstehen keine zusätzlichen Timer oder
Journal-Schreibvorgänge. Neustart setzt die Diagnose zurück. Kumulative
Zeitintegrale und eine neue `collection_id` ermöglichen externe Auswertungen.
Unbekannte Ausgänge und Fallback-Zeiten gelten nicht als bestätigte AUS-Zeit.

Die Werte sind Konkurrenz-Proxys aus HA-Ausgängen, keine Messung von Durchfluss,
Druck, Ventilstellung oder Wärme. Thermische Ventile reagieren verzögert.
Gleichmäßigere Bedingungen könnten Lernen und Regelung verbessern; der Score
allein weist einen solchen kausalen Nutzen nicht nach.

### Historische Auswertung und Langzeitdaten

Der CLI-Aufruf oben arbeitet ohne HA-Installation mit CSV-Dateien oder Ordnern,
expliziten Datensatznamen und JSON-Mapping. Alle IDs und Zeiträume in Beispielen
sind synthetisch. UTC wird intern verwendet; lokale Tage berücksichtigen die
Zeitumstellung. Ein Wiener Tag kann 25 Stunden haben, rollende 24h/7d bleiben
exakt 86.400/604.800 Sekunden.

Unsortierte/duplizierte Zeilen, mehrere Dateien/Gruppen, kurze Impulse und
gleichzeitige Übergänge werden berücksichtigt. Widersprüchliche gleichzeitige
Werte werden unbekannt. Vor dem ersten Zustand wird kein AUS erfunden.
Randimpulse sind gekennzeichnet; kurze Impulse bleiben in Rohsummen enthalten.
Unveränderte Zustände sind nicht automatisch Datenlücken. Unbekannte Zustände,
deklarierte Abdeckungsgrenzen und Wartungsfenster werden explizit behandelt;
nicht dokumentierte Ausfälle können aus CSVs nicht erkannt werden.

Tages-, Impuls-, Gesamt-, Vergleichs- und rollende Ergebnisse werden als CSV und
JSON ausgegeben, einschließlich tatsächlicher Vergleichsfenster. Historische
Tage mit anderem Wärmebedarf sind kein kontrollierter Wirksamkeitsnachweis.
Fehlt eine belastbare unabhängige Referenz, wird kein Vorher-Wert erfunden.

Die verlinkten Template-/ApexCharts-Beispiele verwenden fehlende Werte als
`unavailable`. Recorder/InfluxDB können die Sensoren ohne zusätzlichen
PWM-Speicher erfassen. Für echte 7-Tage-Scores müssen überschneidungsfreie
Zuwächse der Zeitmomente je `collection_id` summiert und daraus Varianz/Score
neu berechnet werden. Tages-Scores zu mitteln oder rollende 24h-Summen zu
addieren wäre falsch. Eine 7-Tage-Anzeige von 24h-Snapshots bleibt eine Anzeige
dieser Snapshots.

### Prüfung und Installation

`--html` ergänzt einen rein offline erzeugten Tabellenbericht mit Zeitband.
Bei fehlender System-Zeitzonendatenbank wird das Python-Paket `tzdata` benötigt.
Das Mapping kann unter `datasets` je Datensatz eigene `start`-/`end`-Werte setzen;
CLI-Grenzen überschreiben diese. `initial_states` sind Startwerte vor dem
Ereignisstrom. Frühere CSV-Ereignisse schreiben sie bis zum Auswertungsbeginn fort.
Zeitlich bestimmte Anfangszustände gehören als Ereignisse in die CSV.

Die Benchmarks vergleichen zwölf synthetische 24h-Verläufe mit der eingefrorenen
Ausgangsversion und prüfen alle Ausgangswechsel und Zeitkonten. Bytewerte sind
serialisierte JSON-Nutzlasten, keine gemessenen Flash-Schreibzyklen. Der echte
HA-Store wird separat außerhalb der HA-Mocks geprüft. ENOSPC ist gezielte
Fehlerinjektion, kein Versuch mit physisch vollem Flash.

Vor Upgrade sichern, HA neu starten und Migration, Gruppenstatus sowie
Zeitkonten kontrollieren. Für Diagnosen gültige Impulse abwarten. Fehlende neue
Journale nicht durch Entfernen des Markers umgehen. Vor Rückkehr zu älterem
Code Zonen sicher stoppen und beide Stores/Sicherungen behalten: das alte
Legacy-Journal ist nach Weiterbetrieb veraltet. Kein Lernreset ist erforderlich.


[Measured validation / Gemessene Validierung](pwm-optimization-validation.md)
