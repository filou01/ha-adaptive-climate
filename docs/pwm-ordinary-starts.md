# Ordinary PWM start entitlement — preview 7

[English](#english) · [Deutsch](#deutsch) · [Documentation index / Doku-Einstieg](fork-extensions.md)

> **Scope / Geltungsbereich:** Historical release/design record; use the [current documentation index](fork-extensions.md) for preview 8. Historischer Versions-/Designbericht; aktuelle Bedienung und Nachweise stehen im Erweiterungsindex. Original test tables and commit/CI references apply to both language sections and retain their original revision context.

## English

`v0.67.1-pwm.7` fixes repeated ordinary OFF→ON transitions within a coordinated
PWM period. It includes the preview-6 restart journal and all earlier fixes.
Coordination remains opt-in; existing YAML and heater services are unchanged.

### Reproduction and root cause

The regression was reproduced against unmodified preview-6 source with real
controllers/HA adapters, for both switch and input_boolean outputs. With a
3600s period, 600s minimum ON/OFF, 120s valve actuation and 21.8% output, the first
effective electrical pulse is 844.8s. After it finishes, a rise to 21.9% adds
only 3.6s of credit. Preview 6 nevertheless sends a second ON after 600s OFF:
two ON edges at relative times 0 and 1444.8s. Both regression instances failed
before the fix (`2 != 1`), and the same assertions now pass.

Positive credit was being used as both a time balance and a start entitlement.
It is insufficient for the latter: even a tiny positive remainder can cause
a new minimum-length pulse. The reported cumulative diagnostic snapshots alone
cannot establish every live trigger, but this reproduces the failure mode.

Inspection also found two related paths requiring protection:

- An expired phase deadline must not grant another allocation in an already
  allocated logical epoch.
- Simply clipping positive post-pulse revisions while retaining all negative
  revisions creates a false debt ratchet under alternating PID fluctuations.

### Behavior

Logical periods use the existing stable group origin, not a rolling cooldown:

```text
epoch = floor((monotonic_now - group_origin) / PWM_period)
```

Every observed OFF→ON spends the ordinary allowance for its actual epoch. An
ordinary controller start also records its ordinary-start epoch. The allocation
separately remembers whether its contiguous pulse has begun, so an already
finished old allocation cannot reopen after the global boundary while waiting
for its next legitimate phase. This distinction matters for delayed/wrapped
pulses. A continuing ON state is not interrupted at a boundary.

An ordinary start requires both an unused period allowance and an unstarted
allocation. PID adjustments, other-zone demand, phase changes, timer callbacks
and minimum-OFF expiry cannot create either entitlement. Minimum-OFF expiry is
only a prerequisite for an otherwise authorized start. Blocked/rejected commands
do not spend the allowance. State and allowance are rechecked after awaited
checkpoint I/O; output observations during that await also consume allowance.

While ON, PID revisions can still adjust the remaining contiguous duration.
After closure, normal PID revisions settle both signs into the signed cancelled
balance rather than reopening the output or ratcheting future debt. Real negative
credit from actual minimum-ON overrun is retained. Future periods calculate
their current demand normally; positive closed-period adjustments are not kept
as a catch-up backlog. Low-duty credit continues earning without repeated
minimum-pulse reservations in an already consumed period.

Deliberate target changes and OFF→HEAT remain explicit exceptions, respecting
minimum times and genuine demand. A priority pulse also consumes the ordinary
allowance; it does not leave permission for an additional ordinary pulse later
that period. Direct 100% remains continuous demand. A priority request blocked
by minimum OFF remains pending until the first eligible instant.

The existing `IMMEDIATE_DEMAND_SPEC.md` explicitly includes true **effective**
target changes from schedules/presets/automations. That contract is retained,
including night-setback effective targets. Plain PID output changes do not
change the target/mode signature and are not priority events. Thus the once-per-
period ordinary rule does not promise one total start if real priority events
or a direct-100% transition occur.

### Restart and journal compatibility

The version-1 PWM journal gains optional fields for `last_start_epoch`,
`last_ordinary_start_epoch`, `allocation_started`, `pending_start_epoch` and
`suppressed_ordinary_starts`. No outer Store/learner version bump or learning
reset is needed. They are included in existing write-ahead/post-confirmation
checkpoints. An uncertain pending ON conservatively spends its possible epoch;
an uncertain ON present at recovery also consumes the recovery period before
being reconciled OFF. This prevents an OFF reconciliation immediately followed
by another ordinary ON in that same period. A new genuine priority change can
still be evaluated with minimum protection.

Preview-6 journals without these fields infer consumed allowance conservatively
from their known output edge and delivery/command history. An OFF edge after a
wrapped pulse can conservatively consume the recovery period even if its ON
began earlier; the following period resumes normally. This can postpone an
ordinary pulse for one period when old history is ambiguous. No missing heat is
invented as a compensating minimum pulse. Partial initialization, repeated
restart, backward-clock rejection and persistence-failure blocking remain.

Malformed entitlement fields fail closed as `restart_state_invalid`. A failed
checkpoint still blocks unjournaled ON and requests safety OFF through
`HeaterController`. Independent/disabled/unsupported fallback retains legacy
timing; the new rule applies while the coordinated group owns the output.

### Diagnostics

| Field | Meaning |
| --- | --- |
| `last_start_epoch` | Latest observed/uncertain ON epoch that consumed ordinary allowance; includes priority starts. `-1` means none known. |
| `last_ordinary_start_epoch` | Latest confirmed ordinary-start epoch, excluding priority/direct-100% starts. Old ambiguous journals can leave this `-1`. |
| `suppressed_ordinary_starts` | Count of positive adjustments/reservations settled because no further ordinary start was available; not a count of issued hardware commands. |
| `remaining_credit_seconds` | Signed remaining balance, including negative real overdelivery. |
| `unmet_debt_seconds` | Positive part only; zero does not imply signed credit is zero. |

The accounting identity remains:

```text
requested_seconds = observed_on_seconds + remaining_credit_seconds
                    + cancelled_balance_seconds
```

The cancelled balance is signed and now also includes revisions to a closed
pulse; it is not simply undelivered positive heat. Helper-state times remain
proxies, not physical relay/flow feedback. Existing restart uncertainty fields
retain [their documented meaning](pwm-restart-safety.md).

### Verification

Tested source/test commit: `eb3062d2bebaf3ce9436872095dfbce105a85b8a`.
The release adds documentation to that identical source/test tree.

| Validation | Result |
| --- | --- |
| Reproduction before fix | 2 failed; both output domains produced two ordinary ON edges |
| New ordinary-entitlement regressions | 54 passed under Windows |
| Full Linux Python 3.11.18 suite | 3682 passed, 11 skipped; exit 0 |
| Full Linux Python 3.12.3 suite | 3682 passed, 11 skipped; exit 0 |
| Full Windows Python 3.14.5 suite | 3671 passed, 11 skipped; 11 existing report-date-format failures (`%b %-d`) |
| Ruff check / format | PASS; 254 files formatted |
| Pyright source | PASS; 0 errors |
| GitHub Linux matrix | [PASS](https://github.com/filou01/ha-adaptive-climate/actions/runs/41922353408) |
| HACS | [PASS](https://github.com/filou01/ha-adaptive-climate/actions/runs/41922353351) |
| hassfest | [PASS](https://github.com/filou01/ha-adaptive-climate/actions/runs/41922353192) |

Tests use actual output transition history and independently computed epoch IDs,
not only entitlement counters. They cover 0.1/0.5/1.0% PID fluctuations, contiguous
ON adjustment, true target/OFF→HEAT/effective-schedule priority, minimum-OFF retry,
phase deadline reuse, stale/minimum-boundary callbacks, delayed and awaited
cross-boundary commands, concurrent calls, checkpoint races, low duty, pauses,
negative-credit accounting, old/current journal recovery and malformed fields.
Existing direct-100%, disabled/legacy, interrupted-command and storage-failure
tests remain in the full suite.

Two new deterministic 24h runs combine four zones, 3600s periods, 600s minimum
ON/OFF and post-pulse PID fluctuations of ±0.1/0.5/1.0 percentage points:

| Result | Minimal | Maximal |
| --- | --- | --- |
| Ordinary ON transitions per zone | 24 / 24 / 24 / 24 | 24 / 24 / 24 / 24 |
| Largest per-zone count in any logical period | 1 | 1 |
| Delivered output seconds | 18835.2 / 17280 / 17280 / 17280 | 18835.2 / 17280 / 17280 / 17280 |
| Group starts | 24 | 24 |
| Highest-weight zone overlap seconds | 5760 | 17280 |

The two strategies preserve identical delivered time and start limits; minimal
keeps lower overlap on the high-weight zone. Every ledger balances with no
positive ending backlog. The earlier eight legacy/comparison and four restart
24h replays also remain in the full suite (14 daily simulations total).

**NOT RUN:** installed-HA/device end-to-end trial, physical NSPanel/ESPHome relay,
pump/flow tests, real power-cut/OS-cache tests, supervised 24h heating,
Raspberry Pi/save-latency/SD-write-volume measurements and wiki publication.
Six existing pytest asyncio-marker warnings remain. These deterministic models
do not prove physical heating delivery or reproduce every trigger in the live
diagnostic snapshots. The broader maintenance-learning case from issue #6 and
the separate dt discrepancy diagnostic remain unchanged.

### Changed files, upgrade and rollback

- `managers/pwm_load_balancing_manager.py`: stable epoch/allocation gates,
  confirmed-edge and write-ahead tracking, closed-budget accounting, diagnostics.
- `managers/pwm_restart.py`: optional entitlement persistence/validation and
  conservative preview-6 inference.
- `tests/test_pwm_ordinary_entitlement.py`: 54 new cases including two daily runs.
- `tests/test_pwm_restart.py`: uncertain-ON recovery now waits for the next
  ordinary period instead of restarting after minimum OFF in the same epoch.
- README, user guide, restart report and PR draft: documentation/evidence.

Back up integration/configuration/learning storage, select
[`v0.67.1-pwm.7` in HACS prereleases](https://github.com/filou01/ha-adaptive-climate/releases/tag/v0.67.1-pwm.7)
and restart HA. Existing YAML, journal data and learning history are retained.
For a monitored upgrade turn participating thermostats OFF and verify outputs
OFF first; the initial no-journal/minimum-time guidance still applies if coming
from a version older than preview 6. No standalone patch or learning reset.

Observe a completed ordinary pulse followed by small PID changes; there should
be no new ordinary ON before a legitimate new period/phase. Verify a true target
change separately, allowing minimum OFF. Do not treat explicit priority starts
as duplicates. Relay timing downstream of a Boolean must be checked separately.

Disable coordination and restart for independent control. Reinstalling unchanged
preview 6 is data-compatible with the additive fields, but it ignores the quota
and reintroduces the repeated-pulse bug; it also drops the new fields on its next
save. Keep the pre-upgrade backup. No upstream PR/issue/comment is opened.

## Deutsch

### Fehlerbild und Ursache

Preview 7 begrenzt gewöhnliche OFF→ON-Starts auf eine Berechtigung je Zone und
logischer Gruppenperiode. Es enthält die Neustartjournale und alle vorherigen
Korrekturen. Die bisherige YAML-Konfiguration bleibt gültig.

Vor dem Fix wurde der Fehler für Switch und Helfer mit echten Controller-/
Adaptergrenzen reproduziert: Bei 3600 Sekunden Periode, 600 Sekunden Mindest-
ON/AUS und 120 Sekunden Ventilfahrt ergibt 21,8 Prozent einen elektrischen Puls
von 844,8 Sekunden. Nach dessen Ende erzeugt 21,9 Prozent nur 3,6 Sekunden mehr
Guthaben, konnte aber nach Mindest-AUS erneut einen vollen Mindestpuls starten.
Beide Regressionstests zeigten zwei statt eines Starts. Positives Zeitguthaben
war fälschlich zugleich als neue Startberechtigung verwendet worden.

Weitere Schutzlücken betrafen eine veraltete Phasenfrist innerhalb derselben
Epoche sowie künstlich anwachsende negative Schuld, wenn nach Pulsende nur
positive PID-Korrekturen abgeschnitten, negative dagegen beibehalten werden.

### Verhalten und Ausnahmen

Die Epoche verwendet den stabilen Gruppenursprung, keinen rollenden Stunden-
Cooldown:

```text
epoch = floor((monotonic_now - group_origin) / PWM_period)
```

Jede beobachtete OFF→ON-Kante verbraucht die gewöhnliche Freigabe ihrer
tatsächlichen Epoche. Zusätzlich wird getrennt gespeichert, ob das aktuelle
zusammenhängende Pulsbudget schon begonnen hat. Ein beendetes altes Budget
darf auch nach einer globalen Grenze nicht erneut anlaufen, während es auf
die nächste rechtmäßige Phase wartet. Durchgehendes ON wird nicht unterbrochen.

Gewöhnliches Einschalten benötigt unbenutzte Periodenfreigabe und ungestartetes
Budget. PID-Änderungen, andere Zonen, Replanning, Timer oder Mindest-AUS-Ablauf
erzeugen keine neue Berechtigung. Abgewiesene/fehlgeschlagene Starts verbrauchen
keine Freigabe. Zustand und Freigabe werden nach wartender Speicher-I/O erneut
gelesen; währenddessen beobachtete Ausgangskanten verbrauchen sie ebenfalls.

Während ON darf sich die zusammenhängende Restdauer ändern. Nach Pulsende
werden normale PID-Korrekturen beider Vorzeichen in der vorzeichenbehafteten
Abschlussbilanz verrechnet. Daraus entstehen weder Nachhol-Minipulse noch
erfundene Negativschuld. Echte Mehrlaufzeit durch Mindest-ON bleibt negativ
erhalten. Niedriglastguthaben kann weiter verdient werden, ohne mehrfach eine
bereits verbrauchte Periode mit Mindestpulsen zu belasten.

Echte wirksame Zieländerungen einschließlich Zeitplan/Preset sowie OFF→HEAT
bleiben Prioritätsausnahmen unter echten Bedarfs- und Mindestzeitgrenzen. Ein
Prioritätspuls verbraucht ebenfalls die gewöhnliche Freigabe. Direkter
100-Prozent-Bedarf bleibt durchgängig. Die Regel verspricht daher nicht genau
einen gesamten Start bei zusätzlichen legitimen Prioritätsereignissen.

### Neustart und Diagnose

Journal v1 erhält optionale Felder `last_start_epoch`,
`last_ordinary_start_epoch`, `allocation_started`, `pending_start_epoch` und
`suppressed_ordinary_starts`. Store-/Lerner-Version und Lernhistorie werden nicht
zurückgesetzt. Ein ungewisser ON-Befehl kann seine mögliche Epoche verbrauchen.
Ist ungewisses ON bei Wiederherstellung vorhanden, darf nach Sicherheits-OFF
nicht allein wegen abgelaufener Mindest-AUS wieder gewöhnlich ON folgen.

Alte Preview-6-Journale werden aus bekannten Ausgangs-/Lieferdaten konservativ
interpretiert. Eine mehrdeutige OFF-Kante nach einem über die Grenze laufenden
Puls kann die Recovery-Periode mitverbrauchen; eine gewöhnliche Periode
Minderlieferung ist dann möglich. Es wird kein künstlicher Ausgleichspuls
erzeugt. Fehlerhafte Freigabefelder führen zu `restart_state_invalid`.
Speicherfehler blockieren unjournalisiertes ON unverändert.

Die Diagnosetabelle und Bilanzgleichung im englischen Teil gelten für beide
Sprachen. `suppressed_ordinary_starts` zählt verrechnete positive Korrekturen,
keine tatsächlich gesendeten Gerätebefehle. `remaining_credit_seconds` und
`cancelled_balance_seconds` sind vorzeichenbehaftet. `unmet_debt_seconds: 0`
beweist nicht, dass das Restguthaben exakt null ist. Helferzeiten bleiben
Stellvertreter für elektrische Anforderung, kein hydraulischer Nachweis.

### Historische Prüfung und Rollout

Quell-/Teststand: `eb3062d2bebaf3ce9436872095dfbce105a85b8a`.
Die Originalmatrix oben dokumentiert 54 neue Windows-Fälle, Linux 3.11/3.12
jeweils 3682 bestanden und 11 übersprungen, Ruff/Format/Pyright sowie GitHub,
HACS und hassfest erfolgreich. Windows 3.14.5 vollständig: 3671 bestanden,
11 übersprungen, elf bestehende Datumsformatierungsfehler.

Zwei neue Tagesmodelle mit vier Zonen, 600 Sekunden Mindest-ON/AUS und kleinen
PID-Schwankungen liefern in beiden Strategien je Zone 24 gewöhnliche Starts
und zusammen 24 Gruppenstarts. Die elektrischen Sekunden sind in beiden Modi
18835,2 / 17280 / 17280 / 17280. Überschneidung mit der höher gewichteten Zone:
5760 Sekunden bei minimal, 17280 bei maximal. Alle Bilanzen stimmen, kein
positiver Endrückstand. Die ursprünglichen acht Vergleichs- und vier
Neustart-Tagesmodelle bleiben enthalten.

Reale HA-/Geräte-End-to-End-Prüfung, physische Panel-/Relais-/Pumpen-/
Durchflussprüfungen, Stromausfall-/OS-Cache-Tests, überwachter Tagesbetrieb,
Raspberry-Pi-/SD-/Speicherlatenzmessung und Wiki-Veröffentlichung waren damals
nicht durchgeführt. Das größere Maintenance-Lernthema und dt-Diagnostik
bleiben außerhalb dieses Fixes.

Vor dem überwachten Upgrade Backup erstellen, beteiligte Thermostate/Ausgänge
OFF prüfen, Vorabversion installieren, neu starten und HEAT fortsetzen. Für
die Kontrolle nach einem beendeten Puls kleine PID-Änderungen beobachten: Kein
zweiter gewöhnlicher ON darf folgen. Echte Ziel-/Moduswechsel separat prüfen.
Preview 6 kann die additiven Daten lesen, ignoriert beim Rollback aber die
Freigaberegel, bringt den Fehler zurück und lässt neue Felder beim Speichern
weg. Für unabhängige Steuerung deaktivieren und neu starten; Backup behalten.
