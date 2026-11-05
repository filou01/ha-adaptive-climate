# Configurable PWM overlap policy

[English](#english) · [Deutsch](#deutsch) · [Documentation index / Doku-Einstieg](../fork-extensions.md)

> **Scope / Geltungsbereich:** Historical release/design record; use the [current documentation index](../fork-extensions.md) for preview 8. Historischer Versions-/Designbericht; aktuelle Bedienung und Nachweise stehen im Erweiterungsindex. Original test tables and commit/CI references apply to both language sections and retain their original revision context.

## English

Historical design decision. The later implemented preview and its supported
configuration are documented in [the user guide](../pump-aware-pwm.md).

Accepted requirement, 2026-11-04. **Design only: no configuration or runtime
scheduler is implemented yet.** See the
[safety review](pump-aware-pwm-safety-review.md) for the unresolved activation
gates. This document supersedes the handoff's single fixed optimization policy
where they conflict.

### User preference

The operator must be able to choose between distributing requested heating
pulses with minimal overlap and concentrating them with maximal overlap. The
requested installation uses **minimal overlap** and accepts increased total
pump energized runtime. Minimizing total pump runtime is not its objective.

This choice belongs to each explicitly configured physical pump group. It does
not replace the disabled-by-default feature flag. Proposed future schema:

```yaml
# DESIGN ONLY. Unsupported by the current integration; do not install in HA.
adaptive_climate:
  pwm_coordination:
    enabled: false
    mode: load_balancing
    groups:
      - name: heating_pump
        overlap_strategy: minimal  # minimal | maximal; planned default: minimal
        handover_overlap_seconds: 240
        max_deferral_seconds: 3600
        zones:
          - entity: climate.zone_a
            hydraulic_weight: 4.0
          - entity: climate.zone_b
            hydraulic_weight: 1.0
```

This is a proposed schema, not an accepted HA configuration. An implementation
must validate it in the real domain schema, reject unknown strategy names,
resolve actual entity identities, and enforce all group compatibility checks.
Changing strategy must invalidate stale plans without restarting active valves
or discarding already delivered heat or accrued credit.

### Shared hard constraints

Both strategies use the same genuine, already authorized effective electrical
ON durations. Neither can add heat to bridge a gap, shorten required delivery,
reset learning or bypass minimum cycle times. OFF, pause, unavailability and
forced-off safety always win. An eligible effective target change or OFF-to-HEAT
must be evaluated immediately, regardless of a future reserved slot. Already
delivered ON seconds replace the displaced reservation exactly once.

The choice affects ordinary subsequent pulse placement only. Safety, delivery,
immediate response, deadlines and accounting precede every optimization goal.

### Strategy objectives

`minimal` prefers spreading the pulses over a larger group energized interval.
Subject to the shared hard constraints, first avoid unnecessary pump starts by
making the group run contiguous when feasible, then minimize simultaneous
electrical occupancy. Prefer keeping high-weight zones alone and allocating
unavoidable concurrency to lower-weight zones. Use the configured handover
overlap as a target where there is sufficient real demand and where it does
not make delivery or timing constraints infeasible.

For fixed total requested electrical time, define redundant occupancy as:

```
sum(per-zone ON seconds) - group energized union seconds
```

Minimizing redundant occupancy increases the energized union up to the available
horizon. High-weight-zone concurrent seconds, then pairwise weighted overlap,
break ties. Required minimum handovers and genuine demand impose a lower bound
on achievable overlap. The target is not a fixed cap: total duty above 100% can
require longer overlaps. No precise hydraulic flow follows from these metrics.

`maximal` prefers concentrating the same requested ON time into a shorter group
energized interval. Subject to the same hard constraints and pump-start goal,
minimize group energized union seconds, allowing high concurrency including
high-weight zones. With unconstrained initially idle zones this often aligns
pulse starts; it must not postpone urgent demand or introduce OFF/ON edges into
an already active pulse merely to align it. Weight-based solo preference is
subordinate to the chosen maximal-concurrency policy.

For example, two zones each requesting 20 electrical minutes in a 60-minute
window could run from 0-20 and 16-36 under a four-minute minimal handover target:
36 estimated pump minutes, four minutes concurrent, one cold start. A maximal
schedule could run both from 0-20: 20 estimated pump minutes, 20 concurrent,
one cold start. Each zone receives 20 minutes in both examples. These examples
omit valve, pipeline and minimum-cycle effects; runtime must use their real
effective durations rather than this illustration.

### Required validation before release

- Both strategies preserve each zone's delivery budget for the 0/40/80/100/
  140/250/400% fixtures and single-zone cases.
- Minimal overlap selects the larger feasible energized union when pump starts
  and hard constraints are equal; maximal overlap selects the smaller union.
- The 140% minimal case preserves the reference high-weight solo preference;
  maximal mode is not required to preserve that soft preference.
- Under 400% demand, both modes remain continuously ON without artificial edges.
- Both run I01-I19, including two-hour future reservations, minimum-OFF retry,
  pauses, failed services, stale callbacks and period-crossing credit.
- Dynamic strategy changes do not duplicate pulses, remove credit or create
  extra active-valve transitions merely for phase alignment.
- The same deterministic 24-hour input trace compares legacy, minimal and
  maximal runs. Report actual per-zone electrical time, estimated pump starts,
  union runtime, concurrency, unmet debt and urgent-response latency. Savings
  must not come from suppressed or delayed immediate heat.

All validation in this section is **NOT RUN**: it specifies future acceptance
criteria, not evidence of existing runtime support.

### Fork and installation status

The personal fork is [filou01/ha-adaptive-climate](https://github.com/filou01/ha-adaptive-climate).
Development is on `codex/pump-aware-pwm`; `main` contains the upstream baseline.
The development branch contains prerequisite tests and engineering documents,
not a HACS-ready implementation of this feature. A future tested release must
include the integration code on an installable fork ref and verified HACS
packaging. No release containing PWM coordination has been created.

No PR to upstream is authorized by this document. The operator intends to
consider one after the fork's implementation is ready and tested.

## Deutsch

### Historische Designentscheidung

Dieses Dokument hält die am 04.11.2026 vereinbarte Strategieauswahl fest. Seine
Aussagen „Design only“, „noch kein Scheduler“ und „kein Release“ gehören zum
damaligen Stand, nicht zum heute vorhandenen Preview 8. Für gültige aktuelle
YAML und Installation gilt die [Anleitung](../pump-aware-pwm.md#deutsch).

Gewünscht war eine Auswahl je ausdrücklich konfigurierter physischer
Pumpengruppe zwischen möglichst geringer und möglichst großer Überschneidung.
Für die angefragte Anlage ist `minimal` bewusst gewählt; längere bestromte
Pumpenlaufzeit wird akzeptiert. Das primäre Ziel ist nicht minimale
Pumpenlaufzeit in Sekunden. Der Vorschlags-YAML-Block oben ist historische
Designsyntax und kein separater aktueller Installationsauftrag.

### Gemeinsame harte Grenzen

Beide Strategien dürfen nur echte bereits zulässige elektrische Heizdauer
verschieben. Sie dürfen keine Wärme erfinden, Mindestzeiten umgehen, bereits
gelieferte Zeit doppelt bezahlen oder Lernen zurücksetzen. OFF, Pause,
Nichtverfügbarkeit und Sicherheits-OFF haben Vorrang. Ein echter wirksamer
Sollwertwechsel oder OFF→HEAT mit zulässigem Puls wird sofort bewertet und
nicht zugunsten weniger Pumpenstarts verschoben. Optimierung folgt danach.

### Strategieziele

`minimal`: Zuerst eine zusammenhängende Laufkette herstellen, soweit echte
Budgets und Timing es erlauben, danach unnötige elektrische Gleichzeitigkeit
vermeiden. Die höher gewichtete Zone soll möglichst allein laufen; längere
unvermeidbare Überlappungen gehören bevorzugt zu kleineren Zonen. Die
Übergabezeit ist bei erfüllbaren Bedingungen ein Ziel und keine starre Obergrenze.
Mehr als 100 Prozent Gesamtlast kann längere Überschneidung erzwingen.

Die redundante Belegung ist die Summe der Zonen-ON-Sekunden abzüglich der
gemeinsamen ON-Union. Weniger redundante Belegung bedeutet bei gleichem Bedarf
eine größere Union. Sekunden gleichzeitigen Betriebs mit der höher gewichteten
Zone und paarweise gewichtete Überlappung dienen als weitere Kriterien.

`maximal`: Dieselbe echte ON-Zeit in einer kürzeren gemeinsamen Union bündeln.
Bei unbeschränkten anfangs inaktiven Zonen werden Starts oft ausgerichtet.
Höher gewichtete Zonen müssen dabei nicht bevorzugt allein laufen. Weder
Sofortbedarf noch aktive Pulse dürfen für diese Ausrichtung verzögert oder
unterbrochen werden.

Zwei Zonen mit je 20 Minuten Bedarf können bei einer Vier-Minuten-Übergabe
minimal 0–20 und 16–36 laufen: 36 Pumpenminuten, vier gleichzeitig. Maximal
können beide 0–20 laufen: 20 Pumpenminuten, 20 gleichzeitig. Beide liefern
20 Minuten je Zone. Das Beispiel lässt Ventil-/Pipeline-/Mindestzeiten weg;
der Produktionspfad muss seine tatsächlichen effektiven Dauern benutzen.

### Damalige Abnahmekriterien

Gefordert wurden die 0/40/80/100/140/250/400-Prozent-Fixtures und Ein-Zonen-
Fälle, vollständige Budgeterhaltung, unmittelbare Priorität, keine künstlichen
Kanten bei 400 Prozent und alle I01–I19-Szenarien einschließlich langer
Vorausplanung, Mindest-AUS, Pausen, Fehlern, veralteten Timern und Grenzübertritt.
Änderungen dürfen keine Reservierung verdoppeln oder aktive Ventile zur
Ausrichtung neu starten. Ein gleicher Tagestrace sollte unabhängige,
minimale und maximale Planung mit Lieferzeit, Starts, Union, Überlappung,
Restbudget und Prioritätslatenz vergleichen.

Diese Liste war beim historischen Design noch nicht ausgeführt. Spätere
Implementierungsnachweise stehen in den jeweiligen Preview-Berichten und im
aktuellen Erweiterungsindex. Weder die damalige Checkliste noch ein späteres
Softwaremodell beweist physische Heizwirkung oder Pumpensicherheit. Fork-`main`
bleibt die Upstream-Basis, Entwicklung liegt auf `codex/pump-aware-pwm`.
Das Dokument ist keine Erlaubnis, einen Upstream-PR zu eröffnen.
