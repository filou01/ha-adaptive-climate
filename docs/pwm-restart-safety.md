# PWM restart journals — preview 6

[English](#english) · [Deutsch](#deutsch) · [Documentation index / Doku-Einstieg](fork-extensions.md)

> **Scope / Geltungsbereich:** Historical release/design record; use the [current documentation index](fork-extensions.md) for preview 8. Historischer Versions-/Designbericht; aktuelle Bedienung und Nachweise stehen im Erweiterungsindex. Original test tables and commit/CI references apply to both language sections and retain their original revision context.

## English

> Preview 7 adds [ordinary-start entitlement recovery](pwm-ordinary-starts.md).
> It also conservatively consumes the recovery period for an uncertain ON present
> at startup; minimum-OFF expiry alone cannot authorize another ordinary pulse.

Repeated HA restarts used to discard the coordinator's period origin and delivery
ledger. A zone could receive a fresh full pulse despite having already completed
one in the same period. Preview `v0.67.1-pwm.6` journals these reservations and
the last known output edge across restarts. Independent legacy PWM still has
its original session-local timing; this change applies to coordinated groups.

### Architecture and guarantees at the HA output boundary

- The existing HA learning Store receives an additive `pwm_coordination` map,
  with a versioned journal per named group. Its outer storage version remains 5
  and the learner payload remains version 12. Existing learning data is retained.
- A checkpoint includes each zone's allocation, delivered/remaining/cancelled
  balance, period/next entitlement, target/mode signature, priority request and
  deferral deadline, last known output edge, earned low-duty credit and valve
  pipeline state. UTC timestamps cross restarts; monotonic timestamps control
  execution within a session. A host reboot resetting monotonic time is tested.
- The journal is saved before commands, after confirmed commands and at control
  reconciliation; orderly shutdown/unload also flushes it. Generation checks run
  again after awaited writes, so a new OFF/target/pause invalidates obsolete ON.
- A completed ordinary pulse is not recreated by a restart. An unfinished pulse
  keeps only its remainder. Missed offline periods are not replayed. Real target
  changes and OFF→HEAT retain priority, including a request blocked by minimum
  OFF before shutdown. Direct 100% remains authoritative continuous demand.
- A previously valid journal can resume already loaded members while other
  members are still loading. It preserves unbound members' rows and never resets
  an earlier restored member when the final entity binds. Fresh groups without
  a journal retain their previous readiness/fallback behavior.
- An ON intent interrupted before confirmation is uncertain. Its reserved
  balance is withdrawn rather than retried as a duplicate. If an uncertain ON
  is present, it is reconciled OFF through `HeaterController` before allocating
  a fresh ordinary period. The new known OFF edge then enforces minimum OFF.
  Eligible direct 100% demand can instead continue ON.
- If storage fails, the group enters `restart_storage_error`, blocks new ON
  through both scheduler and legacy bypass, and requests safety OFF through
  `HeaterController`. Malformed/incompatible journals use `restart_state_invalid`;
  failed uncertain-ON reconciliation uses `restart_reconciliation_failed`.
  These states require investigation/recovery, not repeated blind restarts.

### What cannot be observed during downtime

An unchanged matching output state uses its last known saved edge. A mismatching
state has no reliable edge time, so its minimum-time guard starts conservatively
at recovery. Unobserved ON time consumes at most the outstanding reservation;
it is recorded separately rather than claimed as verified delivery. An uncertain
interrupted command can withdraw its entire remaining reservation, even if the
device never turned ON. This deliberately avoids a duplicate pulse, with possible
under-delivery for that interrupted period. Future periods use current demand.

`restart_uncertain_seconds` reports those uncertain **reserved budget seconds**.
They also form part of `cancelled_balance_seconds`. They are not additional
measured runtime. The balance remains:

```text
requested_seconds = observed_on_seconds + signed_remaining_credit
                    + cancelled_balance_seconds
```

`unmet_debt_seconds` exposes only the positive part of the signed remaining
credit. Zone balance/priority history survives restart; group estimated pump
metrics and generation still begin with the new registry session.

With input_boolean/NSPanel the observed boundary is the helper, not its downstream
relay. The journal does not prove continuous relay state, flow or heat during an
outage. Hidden offline device toggles returning to the same state cannot be
detected. See [the proxy observation limits](input-boolean-pwm.md).

The **first upgrade has no earlier journal** and cannot reconstruct prior-period
delivery from old versions or the user's climate-history CSV. Start the initial
monitored upgrade with thermostats and outputs OFF. Later recorded reservations
are recoverable. If the group falls back to independent legacy control, that
path retains its original restart behavior; this journal is not a general
restart fix for unconfigured/disabled/unsupported thermostats.

### Verification

Final source/test commit: `b0a2ef4a808ebefec498a3acfd3cd0b1a1a03177`.
Release documentation is added without changing that source/test tree.

| Validation | Result |
| --- | --- |
| Windows real-controller restart/storage regressions | 50 passed |
| Full Linux Python 3.11.18 suite | 3628 passed, 11 skipped; exit 0 |
| Full Linux Python 3.12.3 suite | 3628 passed, 11 skipped; exit 0 |
| Ruff check / format | PASS; 253 files formatted |
| Pyright source | PASS; 0 errors |
| GitHub Linux matrix | [PASS](https://github.com/filou01/ha-adaptive-climate/actions/runs/41908013008) |
| HACS | [PASS](https://github.com/filou01/ha-adaptive-climate/actions/runs/41908013026) |
| hassfest | [PASS](https://github.com/filou01/ha-adaptive-climate/actions/runs/41908013030) |

The regressions cover repeated clean/unclean restart, 72-second OFF followed by
a priority request, current-period target changes/OFF→HEAT, a pre-restart blocked
priority request, partial readiness, low-duty credit, active/expired periods,
unknown pending ON, unavailable persistence before/after ON, cancellation during
storage I/O, corrupt counters, backward wall clock and retained learning data.

Four deterministic 24h runs use real controllers/adapters with an in-memory HA
Store, one-hour periods, two 40%-duty zones, weights 4/1, 120s valve travel and
600s minimum ON/OFF. Each switch/input_boolean topology is compared without
restarts and with 143 unclean restarts (every ten minutes; the final journal can
be thirty seconds old). All four runs assert:

| Quantity | No restarts | 143 restarts |
| --- | --- | --- |
| Output ON seconds per zone, external model observation | 36000 / 36000 | 36000 / 36000 |
| Group starts | 24 | 24 |
| Group union ON seconds | 66240 | 66240 |
| Requested seconds per zone | 36000 / 36000 | 36000 / 36000 |
| End remaining credit | 0 / 0 | 0 / 0 |

Thus repeated restart adds neither a pulse nor pump start in this fixed-demand
model. Lost checkpoint observation is classified as uncertain budget, not fake
delivered seconds. The earlier eight legacy-versus-coordinated 24h replays also
remain in the full suite; [their assumptions](architecture/pump-aware-pwm-verification.md)
remain applicable. These are simulations, not measured heating efficiency.

The in-memory replay performs about 5952 journal saves per 24h model at its
30-second/two-zone control cadence. Production saves use the existing learning
Store; SD-card write volume, save latency and Raspberry Pi performance have not
been measured. Persistence adds I/O before starts, but no scheduling-slot wait.

**NOT RUN:** installed-HA restart/debug/device end-to-end testing, physical
NSPanel/ESPHome relay/pump/flow tests, real power-cut/OS-cache failure tests,
supervised 24h hydronic heating, variable maintenance-duty restart simulation
with real actuator timing, full Windows suite for preview 6 and wiki publication.
Six existing pytest asyncio-marker warnings remain.

### Changed files and rollout

- `adaptive/persistence.py`: additive per-group journal load/save under the
  existing Store lock; completed learner data and other group rows are retained.
- `managers/pwm_restart.py`: validated journal/controller codec and recovery.
- `managers/pwm_load_balancing_manager.py`: checkpoint hooks, reservation/command
  ordering, priority recovery and unknown-ON reconciliation.
- `managers/pwm_coordination.py`: initialize/restore/flush journals, controller
  state restoration and persistence-failure safety path.
- `climate_setup.py`, `__init__.py`: initialize under the existing singleton lock
  and flush at shutdown/unload.
- `tests/test_pwm_restart.py`: 50 regression/simulation cases for both domains.
- README, user guide, this report and combined PR draft: documentation/evidence.

Back up integration/configuration/learning storage, select
[`v0.67.1-pwm.6` in HACS prereleases](https://github.com/filou01/ha-adaptive-climate/releases/tag/v0.67.1-pwm.6),
then restart HA. For the initial upgrade first turn participating thermostats OFF
through HA and verify helpers/relays OFF. For this first upgrade, let the
configured minimum OFF time elapse before resuming HEAT; old releases have no
journaled edge to restore. Resume HEAT after startup. Existing
YAML stays valid; do not reset learning data or run standalone patch scripts.

For a monitored check, let a pulse finish, restart in the same period and verify
that ordinary demand does not start the completed pulse again. Then verify a
real target increase responds once minimum OFF permits. Compare helper and real
relay behavior; the integration cannot inspect the latter through a helper.

For `restart_state_invalid`, check restored configuration, storage and system
clock; membership/period/output identity must match the journal. Restore a
known-good storage backup if required. Do not delete the entire learning Store
to clear an error. Disabling coordination and restarting returns to independent
control, whose restart limitation still applies. A code rollback to unchanged
preview 5 is compatible with the additive Store field but ignores the journal
and reintroduces the original repeated-pulse problem. All earlier learning fixes
remain included, including the documented unresolved maintenance-cycle case
from issue #6. No upstream PR/issue/comment is automatically published.

## Deutsch

### Zweck und gespeicherter Zustand

Preview 6 führt Journale für koordinierte PWM-Budgets ein. Zuvor konnte ein
HA-Neustart Gruppenursprung und Lieferbilanz verwerfen und einen bereits
abgeschlossenen Puls derselben Periode erneut vollständig anfordern. Die
Korrektur gilt für koordinierte Gruppen; unabhängige Legacy-PWM behält ihre
bisherige sitzungsbezogene Zeitbasis. Preview 7 ergänzt die Wiederherstellung
der gewöhnlichen Startberechtigung und behandelt ungewisses ON konservativer.

Der bestehende HA-Lernspeicher erhält einen zusätzlichen
`pwm_coordination`-Eintrag mit einem versionierten Journal je Gruppe. Die äußere
Store-Version bleibt 5, die Lerner-Nutzlast 12. Enthalten sind Budget und
gelieferte/restliche/abgeschlossene Sekunden, logische Periode, nächste Freigabe,
Ziel-/Modussignatur, Priorität und Verschiebungsfrist, bekannte Ausgangskante,
Niedriglastguthaben und Ventil-/Pipelinezustand. UTC-Zeitstempel überbrücken
Neustarts; während einer Sitzung wird monotone Zeit verwendet.

Gespeichert wird vor Befehlen, nach bestätigten Befehlen, beim Abgleich und
bei geordnetem Herunterfahren/Entladen. Nach jedem wartenden Speichervorgang
wird erneut auf Invalidierung geprüft. Ein inzwischen eingetretenes OFF,
eine Pause oder Zieländerung kann einen veralteten ON-Befehl widerrufen.

### Wiederherstellung und Schutzgrenzen

Ein fertig gelieferter gewöhnlicher Puls wird nicht neu erzeugt; ein laufender
behält nur seinen Rest. Ausgefallene Perioden werden nicht nachgeholt. Echte
Zieländerungen und OFF→HEAT behalten Priorität, auch bei einer schon vor dem
Neustart durch Mindest-AUS blockierten Anforderung. Direkter 100-Prozent-Bedarf
bleibt durchgängig. Bereits geladene Mitglieder können aus einem gültigen
Journal wiederhergestellt werden, ohne ihre Historie beim späteren Binden der
letzten Zone zurückzusetzen; ungebundene Zeilen bleiben erhalten.

Ein unterbrochener, unbestätigter ON-Befehl ist ungewiss. Sein Restbudget wird
nicht als sicherer erneut abspielbarer Puls behandelt. Vorhandenes ungewisses
ON wird über `HeaterController` OFF abgeglichen, anschließend gilt Mindest-AUS.
Seit Preview 7 kann damit auch die gewöhnliche Freigabe der Recovery-Periode
als verbraucht gelten. Echte neue Priorität bleibt erlaubt. Zulässiger direkter
100-Prozent-Bedarf darf stattdessen ON fortsetzen.

Speicherfehler führen zu `restart_storage_error`: Neue ON-Befehle werden auch
gegen einen unabhängigen Bypass blockiert, ein Sicherheits-OFF wird angefordert.
Ungültige/unpassende Journale melden `restart_state_invalid`; fehlgeschlagener
ON-Abgleich meldet `restart_reconciliation_failed`. Solche Zustände verlangen
eine Ursachenprüfung, keine wiederholten blinden Neustarts.

### Unbeobachtete Zeit und Bilanz

Ein übereinstimmender Zustand nutzt die bekannte gespeicherte Ausgangskante.
Bei Abweichung ist deren Zeitpunkt unbekannt; die Schutzfrist beginnt
konservativ bei der Wiederherstellung. Unbeobachtete ON-Zeit belastet höchstens
die noch reservierte Zeit und wird als ungewiss ausgewiesen. Ein unbestätigter
Befehl kann das ganze Restbudget zurückziehen, selbst wenn das Gerät nie ON
war. Minderlieferung der unterbrochenen Periode ist deshalb möglich; spätere
Perioden berechnen ihren aktuellen Bedarf regulär.

`restart_uncertain_seconds` bedeutet ungewisse reservierte Budgetsekunden,
nicht gemessene zusätzliche Laufzeit. Sie sind Teil der abgeschlossenen Bilanz:

```text
requested_seconds = observed_on_seconds + remaining_credit_seconds
                    + cancelled_balance_seconds
```

Die letzten beiden Größen sind vorzeichenbehaftet. `unmet_debt_seconds` zeigt
nur positives Restguthaben. Zonenbilanzen und Prioritätshistorie überleben den
Neustart, Gruppen-Pumpenschätzungen und Generation beginnen dagegen neu.

Bei NSPanel/ESPHome mit Helferausgang ist nur der Helfer sichtbar. Unbemerkte
Relaisänderungen während des Ausfalls, die zum selben Zustand zurückkehren,
lassen sich nicht rekonstruieren. Das Journal beweist weder Wasserfluss noch
physische Wärmelieferung. Die erste Installation besitzt kein altes Journal
und kann vergangene Lieferung nicht aus alten Versionen oder CSVs erfinden.

### Historische Verifikation

Geprüfter Quell-/Teststand: `b0a2ef4a808ebefec498a3acfd3cd0b1a1a03177`.
Die Originaltabellen im englischen Teil gelten für Preview 6: 50 Windows-
Controller-/Speichertests; Linux 3.11/3.12 jeweils 3628 bestanden und 11
übersprungen; Ruff/Format/Pyright, Linux-Matrix, HACS und hassfest erfolgreich.

Vier deterministische Tagesmodelle verwenden echte Controller/Adapter mit
In-Memory-Store, zwei 40-Prozent-Zonen, Gewichte 4/1, 120 Sekunden Ventilfahrt
und 600 Sekunden Mindest-ON/AUS. Für Switch und Helfer werden jeweils null und
143 ungeordnete Neustarts verglichen. In allen vier Läufen: 36000 ON-Sekunden
je Zone, 24 Gruppenstarts, 66240 gemeinsame ON-Sekunden, 36000 angeforderte
Sekunden je Zone und null Restguthaben. Das beweist keine Heizungs-Effizienz.

Das Modell erzeugt bei seinem 30-Sekunden-/Zwei-Zonen-Takt ungefähr 5952
Journal-Speicherungen pro Tag. SD-Schreibvolumen, Speicherlatenz und
Raspberry-Pi-Leistung wurden nicht gemessen. Nicht durchgeführt waren reale
HA-/Geräte-Neustartprüfung, physische Panel-/Pumpen-/Durchflussprüfung, echte
Stromausfall-/OS-Cache-Versuche, überwachter Tagesbetrieb, variabler Maintenance-
Neustartversuch mit realen Aktorzeiten, vollständige Windows-Suite für Preview 6
und Wiki-Veröffentlichung. Die acht früheren unabhängigen Vergleichsmodelle
behalten ihre dokumentierten Grenzen.

### Installation, Fehlerbehandlung und Rückkehr

Vorher Integration, Konfiguration und Lernspeicher sichern. Beim ersten Upgrade
Thermostate OFF setzen, Helfer/Relais OFF prüfen und Mindest-AUS verstreichen
lassen; frühere Versionen haben keine journalisierte Kante. Passende HACS-
Vorabversion installieren, HA neu starten und HEAT fortsetzen. YAML bleibt
gültig; weder Lernreset noch Zusatzskript ist nötig.

Zur Kontrolle einen gewöhnlichen Puls fertig laufen lassen, in derselben
Periode neu starten und prüfen, dass er nicht wiederholt wird. Eine echte
Sollwerterhöhung separat unter Beachtung von Mindest-AUS prüfen. Helfer- und
echte Relaisstellung getrennt beobachten.

Bei `restart_state_invalid` Konfiguration, Speicher und Systemuhr prüfen;
Mitglieder, Periode und Ausgangsidentität müssen passen. Gegebenenfalls das
bekannte passende Backup verwenden, nicht den gesamten Lernspeicher löschen.
Deaktivieren plus Neustart liefert unabhängige Steuerung. Preview 5 ignoriert
beim Code-Rollback die additive Journalstruktur und bringt das alte Problem
zurück. Die ursprünglichen Quell-/Testdateien und CI-Links stehen oben.
