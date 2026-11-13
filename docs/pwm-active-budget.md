# PWM preview 13: active budget revisions / Laufende Budgetkorrekturen

Version 14 changes the period-concatenation policy described here. See
[Separate PWM pulses / Getrennte Heizimpulse](pwm-start-cadence.md).

## English

Preview 12 could extend a running ordinary pulse after a transient zero demand.
`_allocate()` revoked remaining credit AND erased `allocation`. Minimum ON could
keep the physical output active. A positive output arriving just before the
minimum expired was then treated as an entirely new reservation, rather than a
revision of the already started allocation. `_reconcile()` correctly consumed
the resulting credit; the error was its provenance. A subsequent valid epoch
grant could prolong the same pulse further. The rolling start-spacing guard
does not govern an output that never turned OFF.

Preview 13 retains the revision baseline once an allocation has started. Zero
demand revokes only positive remaining credit and preserves actual negative
minimum-ON debt. A later ordinary revision changes that baseline once. A v12
journal with an already erased, spent baseline cannot authorize a fresh pulse:
the first revision is settled as cancelled until a new epoch or a genuine
target/mode transaction. Continuous demand retains its exception. No new
journal fields, store version, periodic checkpoint or actuator path are added.

### Scheduling invariants

* One grant per observed logical period, at its phase deadline; missed periods
  are never replayed. A changed output revises the current allocation, not the
  amount already delivered. Replanning alone earns nothing.
* `requested = delivered + credit + cancelled_balance`. This is necessary but
  cannot establish that a grant was valid. Delivery means observed electrical
  ON time, not thermal energy or a forecast.
* Valid undelivered credit may cross a period boundary and combine with the
  next period. A late 20% pulse can legitimately last 40% of a period when it
  spends two separately earned grants. There is no universal current-duty cap.
* Zero demand revokes unspent positive time. It cannot erase already delivered
  time, minimum-ON debt, or the identity of a spent ordinary allocation. A
  subsequent positive revision is not a fresh grant of that spent allocation.
* Ordinary starts stay at least one configured period after the last observed
  start; target/mode priority and continuous demand retain their exceptions.
  Minimum ON/OFF and observed-edge attribution remain authoritative.
* A cancelled reservation is not owed heating. A delayed valid reservation is
  still owed; positive credit remaining at a replay cutoff is reported rather
  than silently counted as delivered or lost.

### Why the previous real-data replay missed it

The private v12 runner used the actual production manager and effective pulse
preparation, recorded output/temperature/target/mode changes, phase boundaries
and simulated actuator feedback. Its assertions checked ledger balance,
logical start quotas, minimum switching times and elapsed ordinary-start gaps.
It exported transitions and aggregate delivery, but did not assert contiguous
duration or audit a grant's provenance. Thus a second erroneous grant balanced
perfectly and generated no additional start. The earlier public opt-in replay
also used zero valve/minimum times; it could not reproduce the critical
minimum-ON tail. Neither cold-start replay reconstructed an absent journal.

`tools/replay_pwm_budgets.py` extends the same observed-input approach with the
actual manager, production electrical pulse preparation, minimum times, valve
pipeline and recorded changes during active pulses. It records every allocation
change, period, credit and priority flag, contiguous ON durations, per-zone
delivery and starts/gaps, group starts and hydraulic overlap/consistency. A
separate entitlement account detects resurrection after cancellation instead of
trusting the manager's balanced counters. Its scope is this grant class and
zero-demand debt; it is not a general independent scheduler oracle. Report both
duplicate grant seconds and delivered over/under entitlement; minimum-ON
overrun and still-owed credit must be interpreted separately.

Input format is documented in the module. Raw recordings stay external:

```shell
python tools/replay_pwm_budgets.py --input private-trace.json --output private-results --baseline v0.67.1-pwm.12
```

Use the baseline commit hash if the tag has not been fetched. `profiles` contains
the initial targets/modes; `updates` are time-ordered recorded observations.
`origin` is the relative group phase, `min_raw` defaults to 480 seconds and valve
opening/close-command lead are 120/60 seconds. This runner models 60-minute PWM;
30/60/120-minute behavior is covered by the parametrized manager regressions.
Output snapshots are treated as recorded inputs, not forcibly replayed relay
edges. Compare generated edges with independent observed edges explicitly.

The existing opt-in test accepts `PWM_RECORDED_ELECTRICAL_TRACE` and writes to
`PWM_RECORDED_OUTPUT`; duplicate grants fail the assertion. Synthetic regression
coverage runs in ordinary CI without private data. `test_pwm_active_budget.py`
also exercises real switch/helper adapters and recovery from a v12-shaped
journal, using the existing durable restart harness. That harness covers
restart while ON, monotonic-clock reset, minimum times, priority and safe
checkpoint ordering. The replay CLI does not reconstruct unavailable persisted
state or replay real HA restarts. Do not label its outputs as an exact restored
HA instance or a temperature/comfort/energy forecast.

Counterfactual schedules can change group starts and overlaps even with the
same inputs. Preserving valid credit and the rolling start guard can postpone
delivery. This is a real tradeoff, not guaranteed pump or comfort improvement.
The unchanged 24-hour persistence benchmarks count completed serialized writes
by critical/noncritical/migration category; checkpoint calls are not writes.

## Deutsch

Version 12 löschte bei Nullbedarf nicht nur das restliche Guthaben, sondern
auch die bereits gestartete Budgetbasis `allocation`. Solange Mindest-EIN das
Ausschalten verhinderte, konnte zurückkehrender Bedarf ein vollständiges
zweites Budget erzeugen. Die Bilanz blieb korrekt; die Berechtigung der
Gutschrift war falsch. Eine spätere zulässige Periodengutschrift verlängerte
denselben Impuls weiter. Die v12-Startabstandsregel greift bei einer durchgehend
aktiven Anforderung nicht.

Version 13 erhält die verbrauchte Budgetbasis und negative Mindestlaufzeit-
Schulden. Zurückkehrender Bedarf korrigiert diese Basis einmalig. Alte v12-
Journale mit bereits gelöschter Basis dürfen daraus keine neue reguläre
Anforderung ableiten. Bewusste Sollwert-/Modusänderungen und Dauerbedarf behalten
ihre Ausnahmen. Speicherschema, kritische Relais-Checkpoints und Schreibstrategie
bleiben erhalten.

Die obigen Invarianten unterscheiden Periodenbudget, zulässige Übertragung,
beobachteten Verbrauch und zusammenhängende Laufzeit. Zwei berechtigte Budgets
dürfen weiterhin über eine Periodengrenze zusammenlaufen. Eine starre Grenze
aus aktuellem PID-Prozentsatz mal Periodendauer wäre deshalb falsch.

Der bisherige Echtdaten-Replay führte den echten Scheduler aus, prüfte aber
hauptsächlich Bilanz, Mindestzeiten, Startanzahl und Startabstände. Die doppelte
Vergabe blieb damit unsichtbar: Sie bilanzierte korrekt und erzeugte keine neue
EIN-Flanke. Der einfachere öffentliche Replay ohne Mindest-/Ventilzeiten konnte
die entscheidende Mindest-EIN-Nachlaufphase gar nicht nachstellen.

Der erweiterte Replay protokolliert Budgetänderungen samt Epoche und Priorität,
zusammenhängende Laufzeiten, Heizzeit pro Raum, Startabstände, Gruppenstarts,
hydraulische Überlappung und Konsistenz sowie Über-/Unterlieferung gegenüber
einem separaten Zeitkonto für diese Fehlerklasse. Die bestehenden Restart-
Simulationen testen echte Adapter und persistierte v12-Daten. Rohdaten bleiben
privat; synthetische Regressionen laufen in CI. Das CLI rekonstruiert keinen
fehlenden Produktions-Journalzustand. Unveränderte historische Temperaturen
bilden eine Open-Loop-Simulation und erlauben keine Komfortprognose.
