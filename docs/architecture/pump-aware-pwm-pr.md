# feat: optional pump-aware HEAT PWM coordination

[English](#english) · [Deutsch](#deutsch) · [Documentation index / Doku-Einstieg](../fork-extensions.md)

> **Scope / Geltungsbereich:** Historical release/design record; use the [current documentation index](../fork-extensions.md) for preview 8. Historischer Versions-/Designbericht; aktuelle Bedienung und Nachweise stehen im Erweiterungsindex. Original test tables and commit/CI references apply to both language sections and retain their original revision context.

## English

Independent zone PWM can start a shared electrically OR-controlled pump many
times per day. This change adds disabled-by-default group scheduling with
minimal overlap (spread pulses, favor high-weight solo time) or maximal overlap
(concentrate pulses, potentially trading more pump starts for less runtime).

**An eligible setpoint increase or OFF->HEAT transition is evaluated immediately
and is never delayed to the next coordinated PWM slot; subsequent pulses are
optimized.** Existing safety, genuine demand, minimum switching times and duty
accumulation remain authoritative. Old reservations are revoked and observed
electrical seconds pay the delivery ledger once.

The pure bounded planner issues no HA calls. A domain registry binds live
post-restoration entities to protocol-based group managers. Each group owns one
cancellable next-event timer; controller commands, mode/pause cancellation and
fallback use version checks and a serialized result-bearing heater helper.
Failed/rejected commands do not consume raw credit or emit successful learning
events. Valve/pipeline timestamps follow observed electrical transitions.

The initial preview supports same-period HEAT-only PWM with one non-inverted
`switch.*` or `input_boolean.*` output per zone. Helper proxies report requested
HA state, without downstream relay/network feedback. Unsupported modes/outputs, shared relays, unavailability,
unknown startup ON elapsed time and runtime failure disengage the group with
diagnostics. Unconfigured/disabled installations keep their independent path;
there is no optimizer dependency or pump relay control. The general learning
hotfixes additionally migrate learner payload v11 to v12 to persist its cooldown
cycle counter without discarding completed cycles or confidence.

Configuration, topology assumptions, diagnostics and rollback are in
[the user guide](../pump-aware-pwm.md). Full architecture, changed-file list,
I01–I19 coverage mapping and measured simulation results are in
[the verification report](pump-aware-pwm-verification.md).

The change also integrates the supplied fixes for upstream issues #6 and #7:
transient learning sessions restart consistently, zero/tiny PWM demand shares
one settling deadline, and PID recommendation diagnostics use actual gains.
Recommendation previews preserve cooldown credit; successful application commits
it. Both heater paths are covered. Repeated maintenance output above the 2%
threshold remains outside these narrow fixes. See [hotfix scope and exact-source
validation](../learning-hotfixes.md).

Parallel zone setup now serializes shared learning-store initialization and
restoration before publication, preventing duplicate learning-window number
registration and multiple initial store instances. Six deterministic startup
regressions cover concurrent load/restoration, errors and cancellation.
See [the startup fix report](../learning-startup-fix.md) for exact-source CI links.

Preview 4 accepts `input_boolean` relay proxies (including NSPanel/ESPHome)
through the same controller service and confirmation path. Both domains and
mixed groups are tested; unsupported analog output domains remain rejected.
See [the current compatibility and verification report](../input-boolean-pwm.md).

Preview 5 marks the HA timer, output listener and actuator-confirmation
callbacks for nonblocking event-loop dispatch, correcting executor-thread
access to task creation and scheduler/actuator state. Six new modeled-dispatch
regressions cover both binary domains. The separate dt discrepancy diagnostic
and PID timing remain unchanged; see [the callback fix report](../pwm-callback-safety.md).

Preview 6 adds a versioned per-group PWM journal in the existing HA Store.
It restores period budgets, known delivered time, last known output edges,
low-duty credit and waiting priority/deadline state. Write-ahead ON intents and
post-confirmation checkpoints prevent duplicate ordinary pulses after restart.
Unknown offline delivery is withdrawn into a separate uncertain balance rather
than claimed as measured heat. Failed persistence blocks ON and requests safety
OFF through HeaterController. Partial entity startup retains unbound rows.
See [architecture, changed files, evidence and limitations](../pwm-restart-safety.md).
The initial upgrade has no past journal; independent fallback retains legacy
restart behavior. There is no optimizer dependency or learning reset.

Preview 7 separates ordinary start allowance from signed time credit and
tracks the actual group-origin epoch of observed/uncertain starts. Completed
allocations cannot reopen due to PID noise, stale phase deadlines or minimum-OFF
expiry. Closed-period revisions settle both signs without ratcheting false debt;
real minimum-ON overrun remains signed. Optional quota fields survive restart
and infer preview-6 journals conservatively. Deliberate priority and explicit
effective-target contracts remain; a priority pulse also spends ordinary allowance.
See [reproduction, changed files, compatibility and evidence](../pwm-ordinary-starts.md).

### Validation

Preview 8 repairs executable minimal handovers using signed remaining budgets,
minimum switching bounds and advisory next-period opportunities. Active and
priority starts remain fixed; ordinary allowances and actual delivery are
unchanged. See [the current regression/deployment test plan and exact-source
evidence](../pwm-runtime-handovers.md). The figures below are historical preview 7
evidence and are not a substitute for preview 8 validation.

- Linux Python 3.11.18: **3682 passed, 11 skipped**, full suite, exit 0.
- Linux Python 3.12.3: **3682 passed, 11 skipped**, full suite, exit 0.
- New ordinary-entitlement regressions: **54 passed**, including two 24h PID-noise replays.
- New PWM restart/storage regressions and simulations: **50 passed**.
- New shared-startup regressions: **6 passed** in each full suite.
- New learning hotfix regressions: **29 passed** in each full suite.
- Targeted PWM regressions: **201 passed**, no xfails.
- Ruff check/format and Pyright: **PASS**.
- HACS and hassfest: **PASS** for the preview 7 source commit.
- GitHub Linux 3.11/3.12 matrix: **PASS**, including full tests, lint, format
  and types. Exact-source links and local results are in the ordinary-start report.
- Two additional 24h PID-noise runs: each of four zones starts exactly once
  ordinarily per group-origin period; 24 starts per zone/day and 24 pump starts,
  with identical delivered seconds in both overlap strategies. Minimal limits
  high-weight overlap to 5760s versus maximal 17280s in this model.
- Four additional 24h persistence replays: switch/input_boolean, with zero or
  143 unclean restarts. All preserve 36000 ON seconds per zone, 24 starts and
  66240 group ON seconds, with zero ending debt. Unconfirmed budget is reported
  separately from known observed delivery. Physical behavior is not measured.
- Eight 24h runtime-vs-real-legacy-PWM replays: **PASS** for the measured model.
  At fixed 80% demand, starts fall from 96 to 24 and all four zones receive
  exactly 17280 electrical seconds, with zero debt. At fixed 140%, minimal
  preserves a continuously energized cyclic group; maximal reduces runtime
  but increases starts. Both interactive event latencies are zero simulated
  seconds. Model/finite-window qualifications are explicit in the report.
- Windows full suite: **3671 passed, 11 skipped**, with **11 pre-existing
  report-date-format failures** (`%b %-d`). The new 54 tests all pass; Linux
  passes the report tests. No unrelated reporting changes are included.

**NOT RUN:** real HA automation/preset-to-device end-to-end trial, physical
relays/pump/flow, supervised 24h hydronic run with real minimum times, Raspberry
Pi CPU measurement, variable maintenance-duty 24h replay with real actuator
timing, and wiki publication. Stub/protocol tests do not replace these trials.

### Rollout and rollback

Publish only a clearly marked preview in the personal fork. Keep the feature
disabled initially, preserve learning storage, verify ordinary behavior and
then perform a supervised trial with correct entity IDs and outputs OFF at
startup. Remove the coordination block or set `enabled: false` and restart to
return to independent PWM, which retains legacy restart timing. The first
preview-6 upgrade has no earlier journal; start with outputs OFF and let minimum
OFF elapse before resuming HEAT. Reinstall the recorded upstream version if needed;
do not reset adaptive learning.

No PR is automatically opened upstream. Before an upstream PR, retain reusable
code/tests/docs and adjust fork-specific installation, badge and engineering
history references for the upstream repository. The source version remains
semantic-release managed at its upstream baseline; the fork preview is
identified by its Git tag and exact commit.

## Deutsch

### Umfang des Forks und vorgeschlagene Beschreibung

Dies ist eine vorbereitete Beschreibung der optionalen HEAT-PWM-Koordination,
kein bereits eröffneter Upstream-PR. Unabhängige Zonen können eine gemeinsame
elektrisch ODER-gesteuerte Pumpe häufig neu starten. Der Fork bietet ausdrücklich
aktivierte Gruppen mit minimaler Überlappung für Laufketten und bevorzugten
Alleinlauf großer Zonen oder maximaler Überlappung für konzentrierte Laufzeit.
Standard bleibt deaktiviert. Maximal kann gegenüber bereits durchgängigem
unabhängigem Betrieb mehr Starts erzeugen.

Ein zulässiger echter Sollwertwechsel oder OFF→HEAT wird sofort ausgewertet,
ohne auf den nächsten optimierten Slot zu warten. Echte Nachfrage,
Mindestzeiten, Sicherheit und verdientes Niedriglastguthaben bleiben maßgeblich.
Beobachtete elektrische Sekunden zahlen die Bilanz genau einmal; veraltete
Reservierungen dürfen nicht zusätzlich ausgeführt werden.

Unterstützt sind gleiche positive Perioden, HEAT-only und je ein nicht
invertierter Switch-/Helferausgang. Ein Helfer bestätigt keine nachgelagerte
Relaisstellung. Nicht unterstützte Modi/Ausgänge, doppelte Relais, Ausfälle oder
unbekannte Startzustände führen kontrolliert zum dokumentierten Rückfall.
Nicht konfigurierte Zonen behalten ihre unabhängige Steuerung. Es wird keine
Optimierer-Abhängigkeit und keine direkte Pumpensteuerung eingeführt.

### Enthaltene Weiterentwicklungen

- Preview 1: validierte Gruppen, reiner Phasenplaner, Protokoll-Adapter,
  effektive Reservierungen, ein widerruflicher Timer und serialisierter,
  zustandsbestätigter Aktorpfad.
- Preview 2: enger Lernzyklus-/Settling-Fix, tatsächliche PID-Diagnostik und
  Lerner-Version 12 mit dauerhaftem Cooldown-Zykluszähler. Das größere
  Maintenance-Lernthema bleibt ausdrücklich offen.
- Preview 3: einmalige vollständig abgeschlossene gemeinsame
  Store-Initialisierung vor Veröffentlichung und Number-Entdeckung.
- Preview 4: Helferausgänge und gemischte Switch-/Helfergruppen mit klarer
  Beobachtungsgrenze.
- Preview 5: HA-konforme Event-Loop-Callbacks statt Executor-Zugriffen auf
  Planer-/Aktorzustand und Task-Erzeugung.
- Preview 6: dauerhafte Budget-, Prioritäts- und Mindestzeitjournale sowie
  konservativer Umgang mit ungewissem ON und Speicherfehlern.
- Preview 7: eine gewöhnliche Startfreigabe je Zone und Gruppenepoche,
  zusammenhängendes Pulsbudget, signierte abgeschlossene Korrekturen und
  kompatible Wiederherstellung.
- Preview 8: ausführbare minimale Übergaben aus Restbudget, Schutzgrenzen und
  möglichen Folgefenstern; aktive und priorisierte Starts bleiben fest.

### Prüfbelege richtig lesen

Die große Original-Validierungsliste oben beschreibt Preview 7: Linux
3.11/3.12 jeweils 3682 bestanden, elf übersprungen; 54 neue Freigabefälle,
50 Speicher-/Neustartfälle, sechs gemeinsame Startfälle und 29 Lern-Hotfixfälle.
Die damaligen 14 Tagesmodelle bestanden innerhalb ihrer dokumentierten Grenzen.
Das ist historische Evidenz und nicht die aktuelle Preview-8-Matrix.

Für Preview 8 gilt der verlinkte aktuelle Bericht: 37 neue Tests, lokal 271
PWM-Dateitests und auf Linux 3.11/3.12 jeweils 3719 bestanden/elf übersprungen,
mit bestandenem Lint/Format/Typcheck/HACS/hassfest. Der zusätzliche Tagestrace
reduziert modellierte Starts von 49 auf 25 bei identischen 30000/14400
ON-Sekunden. Der reale HA-Start wurde später begrenzt geprüft; echte
Übergabezyklen und physische hydraulische Abnahme waren damit nicht bewiesen.

Die englischen Tabellen und verlinkten Berichte enthalten alle Quellstände,
Befehle und unveränderlichen CI-Nachweise. Nicht durchgeführte physische,
Tagesbetriebs-, Stromausfall-, Raspberry-Pi-/SD-/Save-Latenz-Prüfungen dürfen
nicht aus grünen Mock- oder Simulationsprüfungen abgeleitet werden.

### Veröffentlichung und Rückkehr

Installation und Rückkehr richten sich nach der aktuellen zweisprachigen
Benutzeranleitung. Vorher Backups, für überwachte Umstellung OFF prüfen,
richtige Fork-Vorabversion wählen und HA neu starten. Keine doppelten
Integrationen derselben Domain, kein Lernreset und keine separaten Patch-Skripte.
Deaktivierte Koordination nimmt allgemeine Lern-/Startkorrekturen nicht zurück.
Ein Code-Rollback muss die jeweilige Journal-/Lerner-Kompatibilität beachten.
Diese Seite allein erteilt keine Erlaubnis, Beiträge im Namen des Nutzers an
Upstream zu senden.
