# Real PWM serialization / Staffelung realer PWM-Anforderungen

## English

### Problem and behavior

The preview-10 minimal planner could overlap two small zones for much longer
than the configured handover target to protect a high-weight zone's later
window. That window could even be an advisory forecast that never became real
demand. A valid two-minute handover between real pulses could lose to a plan
with many minutes of small-zone concurrency.

The repair now ranks **real, executable windows** first:

1. Number of connected pump-ON components.
2. Missing handover overlap, capped by each pulse's duration.
3. Total unweighted pair overlap exceeding the configured handover target.
4. Overlap involving the highest-weight zone, then weighted pair overlap.
5. The existing whole-plan metrics including forecasts, then movement and
   deterministic start ordering.

Forecasts remain useful for connecting otherwise equivalent real plans, but
cannot justify worse real serialization. Unweighted excess comes before zone
weights so transferring a long overlap from a large zone to two small zones
does not hide it. Timing scores are rounded to microseconds to prevent
floating-point cancellation noise from dominating lower-ranked objectives.

The bounded search and its 256 joint-proposal cap remain unchanged. Only
unstarted ordinary pulses move. Active, priority, continuous and forecast
starts remain fixed; forecasts cannot authorize ON. No pulse duration, budget,
minimum time, deadline, persistence format or ordinary-start entitlement is
changed by this repair. The `maximal` strategy does not invoke it.

This is not a hard overlap limit or a global-optimum guarantee. Once both
zones are ON, subsequent real PID budget changes can still extend their
overlap. Cutting heat to force 120 seconds is deliberately outside this fix.
The default remains 240 seconds; configure `handover_overlap_seconds: 120`
explicitly for two minutes.

### Regression and acceptance plan

- Reproduce a fixed future high-weight forecast beside two real small pulses:
  require exactly 120 seconds real overlap, including reversed registration
  order and different forecast weights.
- Reproduce a pending high-weight real pulse: require a complete exact chain
  when bounds allow, including reordering successors. When earliest/latest
  bounds make excess unavoidable, reduce it without crossing those bounds.
- Retain advisory forecasts as tie-breakers for an isolated real pulse.
- Run the existing deterministic 16-zone, CPU, manager, priority, minimum-time,
  budget, restart and persistence tests. Compare real execution metrics for
  non-regression: high-weight overlap alone may intentionally increase.
- Replay identical recorded demand and temperature/PID inputs with identical
  initial conditions. Report starts, parallel time, pump runtime and per-zone
  delivery separately. Open-loop replay cannot predict changed temperatures
  or guarantee comfort, energy savings or invariant delivery under dynamic
  cancellations. Keep all installation data out of the repository.
- During supervised HA acceptance, observe a complete ordinary low-demand
  chain, then a priority change and a constrained chain. Confirm configured
  overlap, minimum ON/OFF times, unchanged heat accounting and no extra
  ordinary start. Separately distinguish post-start PID revisions from
  initially planned excess. Helper edges are not physical pump feedback.

Available in fork test release `v0.67.1-pwm.11` on `test/pwm-storage-hydraulics`.
See [joint handovers](pwm-joint-handovers.md) for the existing search and
[the general test plan](pump-aware-pwm-test-plan.md) for activation/rollback.

## Deutsch

### Problem und Verhalten

Der Minimal-Planer aus Testversion 10 konnte zwei kleine Zonen deutlich länger
als vorgesehen parallel heizen lassen, um ein späteres Fenster der höchst
gewichteten Zone freizuhalten. Selbst eine bloße Prognose, die später keinen
echten Bedarf ergab, konnte eine mögliche Zwei-Minuten-Übergabe verdrängen.

Die neue Bewertung priorisiert echte ausführbare Fenster: zuerst zusammenhängende
Pumpen-EIN-Abschnitte, danach fehlende Übergabe, dann die gesamte ungewichtete
paarweise Überlappung oberhalb des konfigurierten Ziels. Erst anschließend
folgen die Überlappung der höchst gewichteten Zone und die gewichtete
Überlappung. Prognosen unterscheiden nur noch ansonsten gleichwertige reale
Pläne; danach entscheiden Verschiebungsaufwand und stabile Startreihenfolge.
Zeitwerte werden auf Mikrosekunden gerundet, damit Rundungsrauschen keine
fachliche Verbesserung verdrängt.

Die begrenzte Suche mit höchstens 256 gemeinsamen Vorschlägen bleibt erhalten.
Nur ungestartete normale Impulse werden verschoben. Laufende, priorisierte,
kontinuierliche und prognostizierte Starts bleiben fest. Eine Prognose darf
kein EIN freigeben. Heizdauer, Budget, Mindestzeiten, Fristen, Speicherformat
und normale Startberechtigung werden durch die Reparatur nicht verändert.
`maximal` verwendet sie weiterhin nicht.

Nachträgliche PID-Budgetänderungen können bereits begonnene Überschneidungen
verlängern. Der Fix kürzt dafür keine Wärme und garantiert weder eine harte
Obergrenze noch ein globales Optimum. Für zwei Minuten weiterhin ausdrücklich
`handover_overlap_seconds: 120` setzen; der Standard bleibt 240 Sekunden.

### Test- und Abnahmeplan

Die Regressionstests prüfen Prognoseeinfluss, vertauschte Registrierung,
unterschiedliche Gewichte, echte ausstehende Anforderungen, zulässige neue
Reihenfolgen und unvermeidbare Überschneidung bei engen Zeitgrenzen. Eine
isolierte reale Anforderung darf weiterhin eine passende Prognose nutzen.
Bestehende Manager-, 16-Zonen-, Laufzeit-, Prioritäts-, Mindestzeit-, Budget-,
Neustart- und Speichertests bleiben aktiv. Die neue reale Gesamtbewertung
ersetzt dabei die frühere Garantie, allein die größte Zone freizuhalten.

Der Vergleich mit identischen aufgezeichneten Bedarfen und Temperatur-/PID-
Eingaben muss Starts, Parallelzeit, Pumpenlaufzeit und Raum-Heizzeiten getrennt
ausweisen. Ohne thermische Rückkopplung sind weder Komfort noch Energie oder
identische Lieferung bei dynamischen Stornierungen bewiesen. Persönliche
Messdaten gehören nicht ins Repository.

Zur überwachten HA-Abnahme eine vollständige normale Kette bei geringem Bedarf,
eine Prioritätsänderung und einen Fall mit engen Fristen beobachten. Zielwert,
Mindestzeiten, Wärmebilanz und normale Startberechtigung prüfen. Bereits beim
Start geplante Überlappung von späteren PID-Änderungen unterscheiden. Helper
sind keine physische Pumpenrückmeldung. Aktivierung und Rückkehr beschreibt
der verlinkte allgemeine Testplan.

Verfügbar als eigene Testversion `v0.67.1-pwm.11` im Zweig
`test/pwm-storage-hydraulics`. Die ursprüngliche gemeinsame Suche steht in der verlinkten
Dokumentation zu gemeinsamen Übergaben.
