# Pump-aware PWM coordination (preview)

[English](#english) · [Deutsch](#deutsch) · [Documentation index / Doku-Einstieg](fork-extensions.md)

## English

This fork implements optional phase coordination for heating zones whose single
binary outputs energize a shared pump through an existing electrical OR.
Supported outputs are `switch.*` and, since preview 4, `input_boolean.*` relay
proxies (for example, an NSPanel/ESPHome relay following a HA helper).
The feature is disabled by default. It controls zone timing, not the pump relay,
water flow or heat-pump speed. Keep the integration domain `adaptive_climate`.

**Preview status:** software tests and simulation evidence are in the
[verification report](architecture/pump-aware-pwm-verification.md). This is a
supervised-test candidate, not a claim of validation on your heating equipment.

### Configuration

Without this block, or with `enabled: false`, existing independent control is
used. No group scheduling timers or listeners are created when disabled.

```yaml
adaptive_climate:
  pwm_coordination:
    enabled: false  # Enable explicitly only when preparing a monitored trial.
    mode: load_balancing
    groups:
      - name: heating_pump
        overlap_strategy: minimal
        handover_overlap_seconds: 240
        max_deferral_seconds: 3600
        zones:
          - entity: climate.zone_a
            hydraulic_weight: 4.0
          - entity: climate.zone_b
            hydraulic_weight: 1.0
          - entity: climate.zone_c
            hydraulic_weight: 1.0
          - entity: climate.zone_d
            hydraulic_weight: 1.0
```

Merge this into your existing `adaptive_climate:` block; do not duplicate the
top-level key. Use actual climate entity IDs, including registry suffixes.
Weights of 1 are illustrative and do not establish any room's real loop count.

| Setting | Meaning |
| --- | --- |
| `enabled` | Strict Boolean, default false. |
| `mode` | Only `load_balancing` is supported. |
| `groups[].name` | Unique nonempty group name, one physical pump per group. |
| `overlap_strategy` | `minimal` (default) or `maximal`. |
| `handover_overlap_seconds` | Finite 0–1800 seconds, default 240; a target within genuine demand, not extra heater runtime. |
| `max_deferral_seconds` | Finite 0–7200 seconds, default 3600; ordinary phases only. Does not defer urgent demand. |
| `zones` | 2–16 explicit climate entities, unique across all groups. |
| `hydraulic_weight` | Finite, strictly positive; default 1. Ranks concurrency preference, not physical flow. |

Unknown options, duplicate membership, invalid entity IDs and nonfinite numbers
are rejected. Runtime validates actual output identity, period and readiness.

### Choosing overlap

`minimal` arranges a contiguous group run with small handovers, puts the
highest-weight zone first and assigns unavoidable longer overlaps to small
zones. Pump energized runtime can increase relative to concentrating pulses.
At total demand above 100%, long overlap can be mathematically unavoidable.
The 140% reference has a continuous cyclic union and eight minutes of overlap
touching the high-weight zone in each hour.

`maximal` aligns ordinary pulse starts to concentrate the same requested ON
time into a shorter group run. It prioritizes concurrence over high-weight
solo time. It can increase pump starts compared with an already continuous
independent workload. It is not a universal pump-start-minimizing mode.

Both modes preserve the hard safety/delivery rules. Neither adds heat to fill
a pump gap. Handover overlap is electrical overlap; it proves no hydraulic flow.
Changes to group configuration or strategy require a Home Assistant restart.

Preview 8 additionally repairs executable `minimal` handovers from actual
remaining budgets, committed ON intervals, minimum-time bounds and advisory
next-period opportunities. Ordinary pulses can wait within their existing
deadline to avoid an otherwise unnecessary restart. Priority and direct-100%
starts remain immediate subject to the existing minimum protection. See the
[root cause, automated/deployment test plans and limits](pwm-runtime-handovers.md).
The cyclic projections describe an ideal steady-state plan; new `runtime_*`
diagnostics describe the remaining absolute plan, including forecasts. Neither
guarantees continuity when genuine demand changes or a device fails.

### Ordinary pulses

Preview 7 permits at most one ordinary OFF-to-ON transition per zone and stable
group-origin PWM epoch. Each allocation's pulse stays contiguous. Minimum OFF
expiry, PID noise, other zones and replanning do not grant another start.
While ON, demand can adjust remaining runtime. After closure, ordinary demand
revisions settle into the signed cancelled balance; no positive catch-up queue
or artificial negative debt is created. Actual overrun debt remains signed.

True target/mode changes retain priority, including effective schedule/preset
target changes under the original immediate-demand contract. Priority and direct
100% starts are explicit exceptions and still require genuine eligible demand
and minimum protection. Continuing ON across a boundary is not interrupted.
See [period entitlement, diagnostics, restart compatibility and tests](pwm-ordinary-starts.md).

### Immediate demand and accounting

An eligible setpoint increase or OFF->HEAT transition is evaluated immediately
and is never delayed to the next coordinated PWM slot; subsequent pulses are
optimized. Real demand, output availability, pauses and original minimum-cycle
constraints remain authoritative. A minimum-OFF-blocked urgent pulse is retried
at its first eligible instant. Low duty must earn its original accumulator
credit; a target change cannot invent a minimum pulse.

The coordinator reserves effective electrical duration from the original PWM
model, including committed heat, valve travel, early close and effective
minimum ON time. Phase-only replanning reuses that reservation. Observed ON
seconds pay a ledger; a displaced reservation is not played twice. A fresh
eligible target transaction can authorize a new legacy pulse after an earlier
quantum has finished, without erasing already delivered history.

Wrapped pulses carry their remaining credit across the global boundary. The
next entitlement belongs to the zone's next phase, avoiding a duplicate quantum
at the boundary. Delayed callbacks charge elapsed ON time, including overruns;
negative balances offset subsequent demand. OFF/blocked demand withdraws the
remaining reservation and reports the cancelled balance separately.

All commands enter `HeaterController`. Configured supported zones use a
serialized command path with explicit results, bounded service/state waits,
post-await invalidation checks and HA output-state confirmation. Credit and
learning state are not committed for rejected or failed starts. Cancellation
cannot retract a command already sent to a device: an obsolete in-flight ON
is reconciled OFF through the same controller. HA state is an electrical-state
estimate, not proof of valve position or physical heat.

### Compatibility and fallback

| Installation | Behavior |
| --- | --- |
| Feature absent or disabled | Existing independent path. |
| Same-period, HEAT-only PWM, one non-inverted `switch.*` or `input_boolean.*` per zone | Supported preview configuration. |
| HVAC OFF or paused zone | Never used to fill a gap; stale ON reservations are invalidated. |
| Direct 100% demand | Immediate eligible ON, continuous while demand remains full. |
| Cooling, AC, HEAT_COOL, analog valve (`pwm: 0`) | Not coordinated; independent fallback. |
| Multiple outputs or separate demand switches on one zone | Not coordinated in this first preview; existing hardware path retained. |
| Mixed/nonpositive periods, duplicate physical outputs, effective min-ON + min-OFF exceeding period | Group falls back with a reason. |
| Missing members | Independent control until actual entity/controller readiness. |
| Unavailable output, entity rename/removal or scheduler failure | Pending group callbacks revoked; independent ownership restored without mass OFF/ON. |
| Startup ON with unknown elapsed time | Conservative fallback; start the monitored trial with group outputs OFF. |

Fallback is latched for the group until restart. Do not repeatedly toggle
settings to hide a recurrent fault; inspect the exposed reason. Preview 6 adds durable PWM restart journals to the existing HA Store; see
[restart recovery and its limits](pwm-restart-safety.md). No PID gain reset is introduced. Preview 2 adds
an independent learner payload v12 migration; see [learning hotfixes](learning-hotfixes.md).
No obsolete `loops` key or pump-flow-control dependency is introduced. Unconfigured zones are not scheduled.

### Using an input_boolean relay proxy

Keep your existing `heater: input_boolean.wohnzimmer_fbh_heizanforderung`
configuration. A group may contain both switch and input_boolean outputs.
The same `HeaterController` service path, minimum times, priority response,
confirmed HA ON/OFF state and fallback rules apply. Analog outputs, inverted
outputs and multiple outputs per zone remain unsupported for coordination.

With NSPanel-Easy/ESPHome following the helper, HA confirms the **helper state**.
It does not confirm delivery to the panel, its relay position or pump state.
The delivery ledger, valve timing, learning events and pump/overlap estimates
therefore use the helper's ON/OFF transitions as a proxy. Delays, device outages,
manual overrides or extra logic downstream are not detected unless reflected
in the helper state. An available helper does not prove an available panel.
Use this topology only when the downstream relay follows the helper consistently;
no physical relay feedback is inferred by accepting its entity domain.

After upgrading, restart HA because the previous unsupported-output fallback is
latched. Begin the monitored restart with participating thermostats and helpers
OFF, as described below. Preview 6 restores known journaled ON state; startup
ON without a trustworthy journal still falls back.
See [preview 4 verification](input-boolean-pwm.md) for the actual checks run.

### Installing the preview from the fork

1. Back up the existing integration files, YAML configuration and adaptive
   learning storage. Record the current upstream version for rollback.
2. In HACS, use the fork URL
   `https://github.com/filou01/ha-adaptive-climate` as a custom repository of type
   **Integration**. Replace the upstream repository entry rather than installing
   two integrations with the same domain. See
   [HACS custom repository documentation](https://hacs.dev/docs/faq/custom_repositories/).
3. Select the explicitly published PWM preview release rather than the fork's
   upstream-baseline `main`. Enable prerelease visibility if necessary. The
   release notes identify its exact tag, checks and remaining validation gaps.
4. Restart HA with coordination absent/disabled and verify ordinary operation.
5. For a monitored trial, first switch the participating thermostats to OFF
   through HA and confirm their outputs are OFF. Set `enabled: true`, verify
   actual member IDs and equal positive periods, then restart HA. Resume HEAT
   on the participating thermostats and watch the electrical outputs.
6. Test a mid-period setpoint increase and OFF->HEAT. Confirm immediate eligible
   electrical response and monitor temperatures, minimum times and diagnostics.

This page is not a declaration that a particular release has passed tests;
use its verification report. No automatic change is made to your HA instance.

### Diagnostics and rollback

Preview 6 preserves zone time budgets and last known output edges across
restarts. See [restart journals, new diagnostics and limitations](pwm-restart-safety.md).
The first upgrade has no previous journal; independent fallback retains legacy
restart behavior.

Use preview 5 or later for the PWM timer/output callback thread-safety fix. See
[the callback fix and dt-warning assessment](pwm-callback-safety.md) for exact
validation and remaining live-test gaps.


Each participating climate entity exposes a bounded `pwm_coordination`
attribute: group mode/reason, strategy, generation, estimated pump starts and
energized time, projected/observed overlap, requested/observed/cancelled time,
outstanding debt, ordinary deferral and priority latency/blocking information.
Priority latency is command-response timing in the simulation or HA boundary;
it is not time until water reaches the room. No real pump-state sensor is read.

To return to independent PWM, set `enabled: false` or remove the block and
restart Home Assistant. If necessary, reinstall the recorded known-good
upstream release and restore its configuration. Preserve adaptive learning
storage and its pre-upgrade backup; no manual reset is required. See
[the hotfix rollback notes](learning-hotfixes.md#installation-and-rollback) for
the additive learner counter migration.

## Deutsch

### Zweck und aktueller Stand

Diese Fork-Erweiterung koordiniert die zeitliche Lage echter Heizpulse mehrerer
Zonen an einer gemeinsamen Pumpe. Deren vorhandene elektrische ODER-Schaltung
startet die Pumpe, sobald ein Zonenaktor bestromt wird. Die Integration schaltet
nicht direkt die Pumpe und regelt weder Drehzahl noch Durchfluss. Die Funktion
ist standardmäßig deaktiviert. Aktueller Stand ist `v0.67.1-pwm.8`.

Unterstützt werden HEAT-only-PWM-Zonen mit gleicher positiver Periode und je
einem nicht invertierten `switch.*`- oder `input_boolean.*`-Ausgang. Die
Booleschen Helfer können beispielsweise von NSPanel/ESPHome auf ein Relais
übertragen werden. Der Integrationsname bleibt `adaptive_climate`.

### Konfiguration

Der YAML-Block im englischen Abschnitt ist vollständig und gilt unverändert
auch für die deutsche Anleitung. Er wird mit dem vorhandenen
`adaptive_climate:`-Block zusammengeführt; den Schlüssel nicht doppelt anlegen.
Die dortigen Zonen-IDs und hydraulischen Gewichte sind Beispiele und müssen
zur eigenen Anlage passen. Das Gewicht ist eine Optimierungspräferenz und
keine Durchflussberechnung oder automatisch erkannte Heizkreisanzahl.

| Einstellung | Bedeutung und Grenzen |
| --- | --- |
| `enabled` | Strikter Boolean, Standard `false`; ausdrücklich aktivieren |
| `mode` | Nur `load_balancing` unterstützt |
| `groups[].name` | Eindeutiger nicht leerer Name; eine physische Pumpe je Gruppe |
| `overlap_strategy` | `minimal` als Standard oder `maximal` |
| `handover_overlap_seconds` | 0–1800 Sekunden, Standard 240; Ziel innerhalb echten Bedarfs |
| `max_deferral_seconds` | 0–7200 Sekunden, Standard 3600; nur gewöhnliche Pulse |
| `zones` | 2–16 echte Climate-Entity-IDs; keine Mehrfachzuordnung |
| `hydraulic_weight` | Endlich und strikt positiv, Standard 1 |

Unbekannte Optionen, doppelte Mitglieder, ungültige Entity-IDs und nicht endliche
Zahlen werden abgewiesen. Ausgangsidentität, Periode und Bereitschaft werden
zusätzlich zur Laufzeit geprüft. Gruppen- und Strategieänderungen benötigen
einen HA-Neustart. Ohne Block oder mit `enabled: false` gilt die bisherige
unabhängige Steuerung ohne Gruppentimer und Gruppenlistener.

### Die richtige Überlappungsstrategie

`minimal` soll zuerst vermeidbare Pumpenstarts reduzieren, danach kurze echte
Übergaben herstellen und höher gewichtete Zonen möglichst allein betreiben.
Unvermeidbare längere Überschneidungen werden bevorzugt auf kleine Zonen gelegt.
Eine längere gemeinsame Pumpenlaufzeit wird dabei bewusst akzeptiert. Die
Strategie minimiert nicht die Summe aller Pumpen-Einschaltsekunden.

`maximal` bündelt gewöhnliche Pulse für eine kürzere gemeinsame Laufzeit. Das
kann gegenüber einer bereits durchgängigen unabhängigen Last mehr Pumpenstarts
erzeugen; auch diese Strategie garantiert keine universelle Startminimierung.

Beispiel ohne Ventil-/Mindestzeitkorrekturen: Zweimal 20 Minuten echter Bedarf
können bei `minimal` 0–20 und 16–36 Minuten laufen: 36 gemeinsame Minuten,
vier Minuten Überschneidung. `maximal` kann beide auf 0–20 legen: 20 gemeinsame
Minuten, 20 Minuten Überschneidung. Jede Zone erhält gleich viel ON-Zeit.
Bei über 100 Prozent Gesamtbedarf können lange Überschneidungen notwendig sein.
Das historische 140-Prozent-Beispiel ist keine allgemeingültige Lösung.

Preview 8 repariert gewöhnliche Übergaben anhand echter Restbudgets, laufender
Mindest-ON-Verpflichtungen, Mindest-AUS-Sperren und möglicher nächster Freigaben.
Ein noch nicht gestarteter gewöhnlicher Puls darf innerhalb seiner bestehenden
Frist warten oder vorgezogen werden. Eine Zukunftsprognose ist keine neue
Heizberechtigung. Fällt Bedarf weg, können Lücken unvermeidbar bleiben.

### Sofortanforderungen und gewöhnliche Startberechtigung

Eine echte wirksame Sollwertänderung oder OFF→HEAT wird sofort bewertet. Ergibt
die ursprüngliche PWM-Logik einen zulässigen Heizpuls, wartet dieser nicht auf
einen optimierten späteren Slot. Mindest-AUS und andere Schutzgrenzen bleiben
wirksam; ein deshalb blockierter Prioritätspuls wird zur ersten zulässigen Zeit
erneut versucht. Kleine PID-Schwankungen sind keine Prioritätsereignisse.
Ein Sollwertwechsel erzeugt ohne echten Bedarf und verdientes Niedriglastguthaben
keinen künstlichen Mindestpuls. Direkter 100-Prozent-Bedarf bleibt durchgängig.

Seit Preview 7 ist je Zone und stabiler Gruppenperiode höchstens ein
gewöhnlicher OFF→ON-Start erlaubt. Ein zusammenhängendes Pulsbudget kann nach
seinem Ende nicht durch PID-Rauschen oder abgelaufene Mindest-AUS-Zeit erneut
starten. Echte Prioritätsstarts bleiben Ausnahmen und verbrauchen ebenfalls die
gewöhnliche Berechtigung dieser Periode. Bereits laufendes ON wird an der
Periodengrenze nicht künstlich unterbrochen.

### Zeitbilanz und Wiederherstellung

Reserviert wird die wirksame elektrische Pulsdauer der vorhandenen PWM-Logik,
einschließlich Ventilfahrt, Transport-/Pipeline-Effekten, vorzeitigem Schließen
und wirksamer Mindestlaufzeit. Reine Phasenänderungen erzeugen kein zweites
Budget. Beobachtete ON-Sekunden bezahlen die Reservierung genau einmal.

Die Bilanz lautet unverändert:

```text
requested_seconds = observed_on_seconds + remaining_credit_seconds
                    + cancelled_balance_seconds
```

Restguthaben und abgeschlossene Korrekturbilanz sind vorzeichenbehaftet.
Negatives Guthaben kann echte Mehrlaufzeit durch Mindest-ON enthalten und
reduziert nachfolgend geschuldete Zeit. `unmet_debt_seconds` zeigt nur den
positiven Teil; null bedeutet deshalb nicht automatisch Nullbilanz.

Seit Preview 6 werden Budget, Freigaben, Prioritätsfristen und bekannte
Ausgangskanten im vorhandenen HA Store journalisiert. Bekannte bereits
gelieferte Pulse werden durch Neustart nicht wiederholt. Unbeobachtete
Ausfallzeit gilt nicht als nachgewiesene Wärmelieferung. Ungewisse ON-Befehle
werden konservativ behandelt; Minderlieferung einer unterbrochenen Periode ist
möglich. Die erste Installation hat kein früheres Journal. Der Speicher wird
nicht von Hand bearbeitet oder gelöscht. Gruppenmesswerte beginnen nach einem
Neustart neu, während Zonenbilanzen und bestimmte Zähler erhalten bleiben.

### Kompatibilität und Fehlerverhalten

Kühlung, AC, HEAT_COOL, analoge Ventile mit `pwm: 0`, invertierte oder mehrere
Ausgänge je Zone werden nicht koordiniert. Gemischte Perioden, doppelte
physische Ausgänge oder unvereinbare Mindestzeiten führen zum unabhängigen
Rückfall. Fehlende Mitglieder bleiben bis zur tatsächlichen Bereitschaft
unabhängig. OFF oder pausierte Zonen werden nie als Lückenfüller eingesetzt.
Rückfall ist normalerweise bis zum Neustart verriegelt; wiederholtes blindes
Neustarten ersetzt keine Ursachenprüfung. Speicherfehler blockieren neue ON
und verlangen eine sichere Aufarbeitung statt eines unjournalisierten Bypasses.

Ein `input_boolean` bestätigt nur den Helferzustand. Ein ausgefallenes Panel,
verzögerte Relaisübernahme oder manuelle Übersteuerung kann unsichtbar bleiben.
Alle Laufzeit- und Überlappungsschätzungen beziehen sich dann auf den Helfer,
nicht auf nachgewiesene Relaisstellung, Ventilöffnung oder Wasserdurchfluss.
Auch eine elektrische Vier-Minuten-Übergabe beweist keinen Mindestdurchfluss.

### Installation, Kontrolle und Rollback

1. Integrationsdateien, YAML und Lernspeicher sichern; die bisherige Version
   für einen Rollback notieren. Nicht zwei Integrationen derselben Domain
   installieren. In HACS den Fork als benutzerdefiniertes Integrations-Repository
   verwenden und ausdrücklich die passende Vorabversion wählen; Fork-`main`
   enthält die Upstream-Basis, nicht die Preview-Entwicklung.
2. Zunächst den bisherigen Betrieb prüfen. Vor dem überwachten Aktivieren oder
   Upgrade beteiligte Thermostate OFF setzen und Helfer sowie Relais OFF prüfen.
   Beim ersten Upgrade ohne Journal die vorhandene Mindest-AUS-Zeit beachten.
3. Koordination mit tatsächlichen IDs und gleichen Perioden konfigurieren,
   HA neu starten und HEAT fortsetzen. Weder Lernreset noch separate Patch-Skripte
   sind erforderlich. `pwm_coordination.mode` muss `active` werden.
4. Gewöhnliche Übergaben, echten Sollwertwechsel, OFF→HEAT, Bedarfsentzug,
   Periodengrenze und Wiederanlauf getrennt prüfen. Den vollständigen
   [Testplan](pwm-runtime-handovers.md#deutsch) verwenden.
5. Für unabhängige Steuerung `enabled: false` setzen oder den Block entfernen
   und HA neu starten. Bei Code-Rollback die bekannte frühere Version und deren
   dokumentierte Speicherkompatibilität verwenden; Backup behalten.

Die Diagnosefelder, Quellstände und vollständigen historischen Prüfmatrizen
stehen im englischen Teil und den verlinkten zweisprachigen Berichten. Die
neuen `runtime_*`-Werte beschreiben einen Restplan mit Prognosen; die bisherigen
`projected_cyclic_starts` beschreiben einen idealen zyklischen Plan. Keine
dieser Projektionen ersetzt echte beobachtete Schaltkanten. Die automatische
Testabdeckung ist kein Nachweis physischer Pumpen- oder Heizungsvalidierung.
