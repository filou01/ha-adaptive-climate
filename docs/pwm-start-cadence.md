# PWM preview 14: separate pulses / Getrennte Heizimpulse

## Deutsch

Version 14 ersetzt bewusst die in v13 erlaubte Zusammenfassung benachbarter
Periodenbudgets. Ein normaler laufender Heizimpuls bekommt kein zweites
Periodenbudget mehr, nur weil die globale Gruppenperiode wechselt. Das nächste
reguläre Budget richtet sich nach dem letzten tatsächlich beobachteten EIN
derselben Zone plus ihrer konfigurierten PWM-Periode.

Bei konstant 20 % und 60 Minuten PWM entstehen damit einzelne berechnete
Impulse im idealen Abstand von 60 Minuten. Die elektrischen Laufzeiten enthalten
weiterhin Mindestzeiten, Ventilkorrektur, Transport und PID-Revisionen. Die
gemeinsame Serialisierung plant Reihenfolge und Übergaben weiterhin mit dem
vorhandenen hydraulischen Planer, einschließlich 120 Sekunden Übergabeüberlappung.
Pumpenstarts werden innerhalb der zulässigen Startfenster minimiert.

### Verbindliche Regeln

* Eine normale noch nicht ausgeführte Reservierung wird bei verpassten globalen
  Periodengrenzen revidiert, nicht vervielfacht.
* Nach beobachtetem EIN liegt das nächste reguläre Budget frühestens eine
  volle PWM-Periode später. Ein noch laufender gewöhnlicher Impuls erhält
  auch dann kein neues Periodenbudget. Erst nach AUS darf die nächste normale
  Zuteilung erfolgen. Mindest-AUS bleibt maßgeblich.
* Output- und Sollwertänderungen während EIN korrigieren die aktuelle Basis;
  eine globale Grenze macht daraus keinen zweiten Impuls. Ein bewusster
  Sollwert-/Moduswechsel während AUS darf weiterhin priorisieren.
* Echter Vollbedarf bleibt Dauerbedarf. Hohe Last, Mindest-AUS, Kleinstlast-
  Sammlung, fehlender Bedarf und hydraulisch notwendige Verschiebungen können
  den idealen Stundenrhythmus verhindern. Es wird keine künstliche AUS-Flanke
  bei 100 % oder vor Ablauf der Mindest-EIN-Zeit erzwungen.
* Bereits zugeteilte Zeit wird nicht abgeschnitten, um einen Kalendertermin zu
  treffen. Es werden keine verpassten Kalenderbudgets als Nachholzeit angehäuft.
  Dies ist eine geänderte Budgetpolitik, kein Abschneiden gültiger Guthaben.
* Die v13-Korrektur für Nullbedarf und negative Mindestlaufzeit-Schulden bleibt
  erhalten. Bilanz: requested = delivered + credit + cancelled_balance.

Eine jederzeit exakt eingehaltene Stunde und gleichzeitig optimal wenige
Pumpenstarts sind bei wechselndem Bedarf nicht garantiert. Die Startabstands-
und Sicherheitsregeln gehen vor; der bestehende Optimierer koordiniert die
erlaubten Fenster. Kürzere getrennte Impulse können bisherige Pumpenbrücken
entfernen. Deshalb werden Gruppenstarts, Überlappung und Heizzeit separat
verglichen und nicht pauschal als verbessert ausgegeben.

### Persistenz und Einführung

Die vorhandenen Felder last_start_at und next_at reichen aus. Kein neues
Journalformat und keine zusätzlichen periodischen Save-Aufrufe. Die nächste
Budgetgrenze wird mit der tatsächlichen EIN-Flanke verbucht und über den
vorhandenen kritischen Checkpoint gespeichert. Beim Laden eines v13-Journals
wird eine zu frühe globale Grenze vor einer weiteren normalen Vergabe auf
mindestens last_start_at + Periode verschoben. Vor dem Update bereits
zusammengeführtes Guthaben bleibt als bestehende Reservierung erhalten; der
neue Code kann dessen alte Periodenanteile ohne vorhandene Herkunftsdaten
nicht sicher rückwirkend zerlegen. Er hängt kein weiteres gewöhnliches
Periodenbudget daran. Der neue Rhythmus gilt für die folgenden Reservierungen.

Die Diagnose zeigt budget_policy = observed_start_period und
next_budget_in_seconds. next_transition_in_seconds bleibt ein Gruppentimer,
nicht der persönliche Ausschalttermin des Raums.

### Validierung

test_pwm_separate_periods.py prüft 30/60/120 Minuten, beide Strategien,
mehrere aufeinanderfolgende getrennte Impulse, verspätete Startfreigabe,
echte switch/input_boolean-Adapter, v13-Journale und Sollwertänderung während
EIN. Der v13-Test, der zwei Budgets in einem Impuls erwartete, verlangt nun
ausdrücklich getrennte Pulse.

Der bestehende Echtdaten-Auditor zählt nun zusätzlich
active_ordinary_period_grants; diese Liste muss für v14 leer sein. Die bisherigen
Bilanz-, Mindestzeiten-, Startabstands- und Nullbedarfsprüfungen bleiben aktiv.
Vergleiche führen den unveränderten v13-Manager aus seinem Release-Commit und
den neuen v14-Manager mit denselben historischen Eingaben aus. Die private
Wohnzimmeraufnahme reproduziert 1.750,8 Sekunden unter v13 und 841,2 Sekunden
unter v14. Historische Temperaturen bleiben fest: Open Loop, keine Komfort-
oder Energieprognose. Echte Restart-Tests ergänzen das Kaltstart-Replay.

## English

Preview 14 deliberately replaces preview 13's adjacent-period concatenation.
An ordinary running pulse no longer receives another period's grant at the
shared group boundary. Its next ordinary entitlement follows the actual
observed ON plus one configured PWM period, and waits until the output is OFF.
One pending, unstarted reservation is revised rather than multiplied across
missed group epochs. This avoids a backlog of calendar grants.

At constant 20% and a 60-minute period, isolated pulses ideally start every
60 minutes. Electrical duration still includes the existing minimum times,
valve/transport model and output revisions. The existing hydraulic runtime
planner continues coordinating serial order and handover overlaps within valid
start windows. A target change while ON revises the same allocation; a genuine
target/mode change while OFF retains the priority exception.

Continuous full demand, minimum ON/OFF, low-duty accumulation, absent demand and
hydraulic deferral remain legitimate exceptions to an exact hourly cadence.
There is no forced artificial OFF at 100% or before minimum ON. Separate pulses
can remove pump bridges; pump-start savings and unchanged thermal comfort are
not guaranteed. Report electrical delivery and hydraulic effects separately.

No journal field, storage version, periodic save call or PID formula is added.
Existing observed-start and next-budget timestamps persist through the critical
checkpoint. Old v13 phase deadlines are guarded by the observed start interval.
Already merged legacy credit is preserved; its missing historical provenance
cannot safely be reconstructed retroactively. Further ordinary period grants
cannot extend it. The v13 transient-zero fix and signed minimum-ON debt remain.

New regressions cover 30/60/120-minute periods, both overlap strategies,
multi-period observed cadence, delayed starts, real adapters, v13 journal
recovery and active target revisions. The recorded-input auditor additionally
reports active_ordinary_period_grants, which must be empty under v14. Existing
delivery, spacing, minimum-time and hydraulic checks remain. Compare exact
v13/v14 source versions with identical private inputs. This is an open-loop
electrical replay, not a temperature, comfort or energy forecast.
