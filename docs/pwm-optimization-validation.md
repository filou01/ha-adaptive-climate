# PWM optimization validation / Validierung der PWM-Optimierung

[English](#english) · [Deutsch](#deutsch)

## English

### Reproducible scope and results

The frozen coordinated runtime is `e2501cb44805f58b40532a1db6861882fa29b1a3`.
The same benchmark harness runs against that source and the optimized runtime.
Four synthetic zones have weights 4/1/1/1 and ordinary demands 720/540/360/360
seconds per hour. Idle, continuous demand, PID noise and priority traces override
the corresponding inputs. Both strategies and 60s/10s updates are represented.
These are deterministic electrical/accounting replays, not measured thermal energy.

| 24h trace | Completed writes before → after | Payload bytes before → after | Host replay seconds before → after |
| --- | ---: | ---: | ---: |
| continuous-60-maximal | 5793 → 1453 | 113185634 → 4845652 | 4.80 → 1.46 |
| continuous-60-minimal | 5816 → 1476 | 113625368 → 4919252 | 4.96 → 1.51 |
| idle-60-maximal | 5785 → 4 | 112333130 → 22704 | 4.49 → 0.83 |
| idle-60-minimal | 5785 → 4 | 112333130 → 22704 | 4.54 → 0.88 |
| noise-10-maximal | 35013 → 20002 | 688025572 → 69303952 | 29.16 → 11.08 |
| noise-10-minimal | 35110 → 23513 | 691528424 → 82105128 | 32.95 → 15.27 |
| priority-60-maximal | 6249 → 619 | 121889369 → 2060818 | 5.03 → 1.15 |
| priority-60-minimal | 6331 → 723 | 123471428 → 2395998 | 5.30 → 1.39 |
| steady-10-maximal | 35049 → 2051 | 682578851 → 6745663 | 29.09 → 6.41 |
| steady-10-minimal | 35139 → 3245 | 684541462 → 10652467 | 30.32 → 7.44 |
| steady-60-maximal | 6249 → 611 | 121706623 → 2016726 | 5.14 → 1.14 |
| steady-60-minimal | 6339 → 725 | 123493874 → 2387060 | 5.40 → 1.34 |

All 12 pairs have **exactly identical zone transitions and signed delivery ledgers**.
Reconstructed pump starts, ON union, hydraulic moments and weighted overlap are
therefore unchanged by this optimization. No new delay is introduced for active
consumption checkpoints. The 80% write-reduction goal is exceeded by steady and
idle traces; continuous demand and genuinely changing PID entitlements retain
more writes because restart correctness takes precedence.

Counts include initial migration and final shutdown; unchanged idle operation has
no repeated writes. Bytes count completed compact JSON payloads in a counting
Store harness, not filesystem block writes, HA envelope bytes or physical flash
wear. Baseline learning data are synthetic histories, so byte savings depend on
the installed learning dataset. Host wall times include Python work and simulated
serialization; they are neither isolated CPU measurements nor Raspberry Pi claims.

Representative `steady-60-minimal`, same coordinated scheduler before/after:

| Metric | Before | After |
| --- | ---: | ---: |
| Completed Store writes / 24h | 6339 | 725 |
| Serialized payload bytes / 24h | 123493874 | 2387060 |
| Reconstructed pump starts / 24h | 24 | 24 |
| High-weight-zone HC | 81.144 | 81.144 |
| High-weight-zone solo time (%) | 66.667 | 66.667 |
| Pair-product weighted overlap (weight²·s) | 37440.0 | 37440.0 |
| Heating delivery deviation | 0 s | 0 s |
| Observed conservation violations | 0 | 0 |

Full machine-readable evidence, including critical/noncritical classifications,
checkpoint/reconcile counts and each zone's observations, is in
[the synthetic benchmark directory](benchmarks/pwm-optimization/).
Pump counts use `[0, 86400)`; terminal boundary persistence is included in write
counts but an ON at exactly 86400 is not an extra start inside the reported day.

### What hydraulic evaluation demonstrates

The metric is not a universal scheduling-quality score. Eight controlled replays
also compare the actual independent PWM controller with coordinated scheduling.
In a high-demand interactive minimal trace, starts fall 19 → 3, high-weight-zone
HC rises 69.72 → 82.11, solo time rises 31.48% → 72.38%, and weighted overlap falls
223680 → 71580 weight²·s. In a lower-demand interactive minimal trace, starts fall
54 → 23, HC rises 72.63 → 82.90 and solo time rises 40.48% → 77.58%.

Counterexamples matter: fixed independent non-overlapping pulses have HC 100 and
100% solo time; joining them in a minimal chain reduces starts 96 → 24 but HC
falls to 81.14 and solo time to 66.67%. Maximal alignment can increase starts
for a formerly continuous group (1 → 24) while reducing its energized window.
Stable overlap can score 100 with zero solo time. These trade-offs are preserved,
not optimized away to improve a synthetic score. No causal PID-learning, energy,
physical flow or equipment-lifetime improvement is claimed from these replays.

Historical CSV comparisons require explicitly labeled independent/coordinated
datasets and their actual windows. No personal production histories are committed.
A missing independent baseline or less than seven days of coverage must remain
unavailable; neither version labels nor missing observations are inferred from dates.

### File-by-file review map

| Files | Review purpose |
| --- | --- |
| `managers/pwm_storage.py` | Compact acknowledged Store, semantic signature, serialized migration, cancellation drain. |
| `managers/pwm_coordination.py` | Await initialization/migration, bind safely, journal callback and shutdown barriers. |
| `adaptive/persistence.py`, `climate_setup.py` | Share one learning Store and setup lock; marker cannot be overwritten by another Store instance. |
| `managers/pwm_load_balancing_manager.py` | Critical flag, plan/deadline reuse, callback tokens, event-driven diagnostics. |
| `helpers/hydraulic_metrics.py` | Shared interval moments, pulse/coverage logic, bounded live collection. |
| `tools/analyze_hydraulic_consistency.py` | Offline labeled CSV/daily/rolling comparison and optional HTML report. |
| `tools/report_pwm_benchmarks.py` | Exact behavioral comparison and reproducible synthetic evidence. |
| `tools/verify_pwm_store.py` | Real HA storage failures, race/cancellation/shutdown probe, real Template validation. |
| `tests/pwm_benchmark_support.py`, `test_pwm_persistence_benchmark.py` | Opt-in 12-trace counting benchmark. |
| `tests/test_pwm_persistence_policy.py`, `test_pwm_restart.py`, `test_learning_startup.py` | Migration, restart phases, failures, shared initialization and unchanged learner data. |
| `tests/test_hydraulic_metrics.py`, `test_hydraulic_history.py`, `fixtures/hydraulic_history/` | Analytic weights, CSV fixture, UTC/DST, simultaneous handovers, gaps and rolling windows. |
| `examples/pwm-hydraulic-*` | Generic mapping, optional HA sensors and ApexCharts configuration. |
| `.github/workflows/pwm-validation.yml` | Full Linux 3.11/3.12 regressions/lint/types and real HA 2026.11.0 on Python 3.14. |
| `docs/pwm-persistence-and-hydraulics.md`, this page | Bilingual design, deployment, rollback, evidence and limitations. |

Source paths in this table are relative to `custom_components/adaptive_climate/`
unless prefixed with `tools/`, `tests/`, `examples/`, `.github/` or `docs/`.
The existing upstream 0.67.1 `_command_verify_timer` and this feature's timer
version guard are both retained when merging current main.

### Validation and acceptance plan

The full Linux suite, Ruff check/format and Pyright run on the actual feature
branch, not a source-modified validation copy. The real-HA probe runs separately
from pytest's HA mocks and checks successful atomic readback, serialization
failure, injected ENOSPC, a real permission failure, exact-payload acknowledgement
under delayed-save races, cancellation drain and rejected shutdown-deferred saves.
It validates Template schema and availability including legitimate zero scores.
See [branch workflow runs](https://github.com/filou01/ha-adaptive-climate/actions/workflows/pwm-validation.yml).

Restart regressions cover before intent, after intent/before actuation, after
actuation/before confirmation, confirmed delivery, min-OFF, repeated restarts,
long downtime, corrupt/missing journals and storage failures. Existing low-duty,
priority, minimum-time, stale callback, epoch and ledger regressions remain enabled.
Windows retains the same 12 baseline platform/real-clock failures; Linux is the
authoritative full-suite environment. Opt-in benchmarks skip in everyday CI.

For supervised HA acceptance, follow the existing
[test plan](pump-aware-pwm-test-plan.md) and the
[migration/rollback notes](pwm-persistence-and-hydraulics.md#validation-and-deployment).
Specifically verify both strategies, first migration/restart, no repeated idle
journal writes, normal pulses, immediate eligible priority response, unknown
outputs, and missing-storage fallback without bypassing the marker. Inspect
`pwm_coordination.hydraulic_consistency` only after sufficient valid observations.
This task does not install the code or restart a user's HA instance.

The HA acknowledgement hook is private and pinned to an actual tested HA version;
future HA changes need this probe. Atomic replacement is not a guarantee against
every power-loss mode. Hydraulic diagnostics reset on restart and are output-state
proxies, not physical actuator/flow measurements. Hidden Recorder downtime cannot
be recovered from transition CSVs without explicit coverage/exclusion metadata.

## Deutsch

Die Tabellen oben enthalten echte Messwerte aus zwölf deterministischen,
synthetischen 24h-Wiedergaben. Die eingefrorene Ausgangsversion ist `e2501cb`.
Alle Ausgangswechsel und vorzeichenbehafteten Zeitkonten sind vor/nach der
Optimierung exakt gleich. Pumpenstarts, Wärmelieferzeiten und hydraulische
Beobachtungen bleiben dadurch erhalten. Es gibt keine neue Wartezeit für laufende
Verbrauchsabrechnung und keine zusätzlichen Diagnose-Speicherungen.

Im repräsentativen Minimal-Fall sinken die Schreibzahlen von 6339
auf 725 und die Nutzlast von 123493874 auf
2387060 Byte. Dauerbetrieb und echte Budgetänderungen behalten mehr
Schreibvorgänge als das 80%-Ziel: Sicherheit hat Vorrang. Unveränderter Leerlauf
schreibt nicht wiederholt; die vier gezählten Vorgänge enthalten Migration,
ersten Zustand und Abschluss. Die CSV/JSON-Dateien enthalten alle Zonen,
kritische/nichtkritische Vorgänge, Abgleiche und Laufzeiten. JSON-Bytezahlen sind
keine physischen Flash-Schreibzyklen; Host-Laufzeiten sind keine isolierte
CPU- oder Raspberry-Pi-Messung. Die synthetische Lerndatenmenge beeinflusst die
Byte-Ersparnis.

Der separate Vergleich mit unabhängiger PWM zeigt Vorteile und Grenzen der
Koordination. Bei interaktivem hohem Bedarf im Minimal-Modus: 19 → 3 Starts,
HC 69,72 → 82,11, Alleinlauf 31,48% → 72,38%. Bei bereits perfekt getrennten
festen Impulsen: 96 → 24 Starts, aber HC 100 → 81,14 und Alleinlauf 100% → 66,67%.
Maximales Ausrichten kann eine vorher durchgehend laufende Gruppe häufiger
starten lassen. Der Score belegt weder reale Durchflussverbesserung noch bessere
PID-Lernwerte, Energieeinsparung oder Lebensdauer. Die Speicheroptimierung selbst
verändert diese Zielkonflikte nicht.

Die Dateitabelle ordnet jede Änderung ihrem Prüfzweck zu: kompakter bestätigter
Store und Migration, gemeinsame Initialisierung, Plan-/Timerwiederverwendung,
gemeinsamer Metrikkern, Offline-Werkzeuge, Regressionen und optionale HA-Beispiele.
Der aktuelle Hauptzweig 0.67.1 ist integriert; dessen Befehlsbestätigungstimer und
die Versionssicherung dieses Features bleiben beide erhalten.

Linux prüft die gesamte Suite unter Python 3.11/3.12 mit Ruff und Pyright. Der
separate echte HA-Store-Test unter HA 2026.11.0 prüft Schreibbestätigung,
Serialisierungsfehler, injizierten vollen Datenträger, echte Berechtigungsfehler,
verzögerte konkurrierende Speicherungen, Abbruch und Stoppen sowie echte
Template-Schemas und Verfügbarkeit einschließlich 0. Die Neustarttests prüfen
alle Intent-/Aktuierungs-/Bestätigungsphasen, Mindest-AUS, wiederholte Neustarts,
lange Ausfälle sowie fehlende/beschädigte Journale. Bestehende Regressionen bleiben
aktiv. Unter Windows verbleiben dieselben zwölf Plattform-/Echtzeitfehler der
Ausgangsversion; maßgeblich ist die vollständige Linux-Prüfung.

Für Installation/Abnahme gelten der verlinkte zweisprachige Testplan und die
Migrations-/Rollback-Hinweise: beide Strategien, Migration, Neustart, Leerlauf,
Priorität und Speicherfehler prüfen. Das Entfernen des Markers ist kein
zulässiger Fehler-Workaround. Diese Arbeit installiert nichts auf HA.

Private Produktionsdaten bleiben außerhalb des Repositorys. Ohne unabhängigen
historischen Datensatz wird kein Vorher-Vorteil erfunden; ohne sieben Tage
Abdeckung bleibt die echte 7-Tage-Auswertung nicht verfügbar. CSVs benötigen
explizite Versionsnamen, Zeiträume und bekannte Ausfallfenster. Der private
HA-Bestätigungshook muss bei HA-Updates erneut geprüft werden. Atomarer Austausch
deckt nicht jeden Stromausfall ab; Diagnosen werden bei Neustart zurückgesetzt
und messen HA-Ausgänge statt physischer Ventile oder Wassermengen.
