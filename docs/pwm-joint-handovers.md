# Joint PWM handovers / Gemeinsame PWM-Übergaben

## English

Preview 10 on the fork test branch adds a bounded joint-move neighborhood to
the existing executable repair. Preview 9 could retain almost simultaneous small
zone starts even when a valid chain had the same pump start count and heat grants.
Moving either pending pulse alone temporarily worsened a higher-ranked objective;
the original coordinate search therefore rejected both intermediate moves.

The repair now evaluates up to 256 additional two-pulse chain proposals when
excess overlap and at least two movable ordinary pulses exist. It accepts only
a strictly better plan under the unchanged objective: pump components, handover
shortfall, high-weight overlap, weighted overlap, then movement. Both changes
are assessed atomically. This is bounded local search, not a global optimum.

Only unstarted ordinary windows move. Active, priority, continuous and forecast
windows stay fixed. A forecast cannot grant heat or authorize ON. Durations,
earliest/latest bounds, minimum-time constraints and original deferral deadlines
are retained. Scheduling never creates a second ordinary allowance to improve
a chain. Maximal scheduling does not invoke this minimal-strategy repair.

### Reproduced synthetic counterexample

| Metric | Preview 9 | Preview 10 |
| --- | ---: | ---: |
| Target handover | 120s | 120s |
| Pump components | 1 | 1 |
| Handover shortfall | 0s | 0s |
| Large-zone overlap | 120s | 120s |
| Small-zone pair overlap | 597s | 120s |
| Weighted overlap (weight²·s) | 1225 | 600 |
| Changed heat durations or window bounds | 0 | 0 |

The 240s variant reduces weighted overlap from 2185 to 1200, again with one
component and unchanged grants/bounds. This deterministic model proves the
search correction, not physical flow or a historical reconstruction of an
installation. Earlier persistence benchmark tables describe the pre-preview-10
storage optimization; identical old/new scheduling is not claimed for this
intentional phase-planning correction.

### Configuration and acceptance

**For two-minute handovers set `handover_overlap_seconds: 120` explicitly.**
The compatibility default remains 240s and an explicit 240s setting is honored.
Installing preview 10 does not rewrite HA YAML. Check the actual configured
value in `pwm_coordination.handover_overlap_seconds` after restart.

The target applies where a chain is feasible. Real priority, changing active
budgets, minimum times, excess total demand and deadlines can still require
deviations. Do not cut earned heat or delay eligible priority heat for cosmetic
120s intervals. HA service/event latency can add timing jitter.

Regression coverage includes both targets, reversed registration order, fixed
active/priority/forecast starts, tight latest-start bounds, short pulses, zero
overlap and manager-level integration without executing forecast ON commands.
The existing 16-zone bounds/determinism/CPU guards, restart, priority, ordinary
allowance, HA/controller boundary and 24h comparisons remain enabled.

For supervised acceptance, use the existing test plan, then check a complete
ordinary chain at comparable low demand: short handovers, unchanged pulse
duration/credits, no extra ordinary start, and no extra pump component. Separately
exercise priority changes and constrained/high-demand periods. Compare helper
edges and runtime reasons; these are not physical valve or pump feedback.
Rollback to preview 9 retains the dedicated-store format. Rollback to preview 8
or original PR code requires the older-code migration precautions in the
[persistence guide](pwm-persistence-and-hydraulics.md).

## Deutsch

Vorabversion 10 im eigenen Testzweig ergänzt begrenzte gemeinsame Verschiebungen
zweier ungestarteter Impulse. In Version 9 konnte der Planer parallele kleine
Zonen beibehalten, obwohl eine gültige Kette dieselben Pumpenstarts und
Wärmebudgets hatte: jede einzelne Zwischenverschiebung verschlechterte zunächst
ein höher bewertetes Ziel. Beide Änderungen werden jetzt gemeinsam bewertet.

Bei zu großer Überlappung und mindestens zwei beweglichen normalen Impulsen
werden höchstens 256 zusätzliche Vorschläge geprüft. Nur ein strikt besserer
Plan wird übernommen. Die Reihenfolge der Ziele bleibt unverändert: Pumpen-
komponenten, fehlende Übergabe, Überlappung der größten Zone, gewichtete
Überlappung, danach Verschiebung. Ein globales Optimum wird nicht behauptet.

Laufende, priorisierte und kontinuierliche Impulse sowie Prognosegelegenheiten
bleiben fest. Eine Prognose darf weiterhin keinen EIN-Befehl freigeben. Dauer,
Zeitgrenzen, Mindestzeiten, Aufschub und Startberechtigung bleiben erhalten.
Die Strategie `maximal` verwendet diese Minimal-Reparatur nicht.

Die Tabelle oben zeigt den synthetischen Zwei-Minuten-Fall: 597s Überlappung
zwischen kleinen Zonen werden zu 120s; gewichtete Überlappung 1225→600. Es bleibt
bei einer Pumpenkomponente, identischen Heizdauern und Zeitgrenzen. Bei 240s
Ziel sinkt die gewichtete Überlappung 2185→1200. Das ist ein Softwareversuch,
keine historische Anlagenrekonstruktion oder Durchflussmessung. Die älteren
Speicher-Benchmarks gelten als Nachweis der Optimierung vor Version 10; für
diese bewusste Planungskorrektur wird keine unveränderte Schaltfolge behauptet.

**Für zwei Minuten ausdrücklich `handover_overlap_seconds: 120` konfigurieren.**
Der kompatible Standard bleibt 240s; ein gesetzter 240s-Wert wird respektiert.
Das Update schreibt keine HA-Konfiguration um. Nach Neustart den tatsächlichen
Zielwert in `pwm_coordination.handover_overlap_seconds` prüfen.

Prioritäten, laufende Budgetänderungen, Mindestzeiten, hoher Gesamtbedarf und
Fristen können weiterhin andere Überschneidungen erfordern. Dafür weder echte
Wärme kürzen noch zulässige Sofortanforderungen verzögern. Dienste und
Ereignisschleife können reale Zeitabweichungen verursachen.

Die Tests decken beide Zielwerte, umgekehrte Registrierung, feste Startfenster,
knappe Fristen, kurze Impulse, Zielwert null und die Einbindung im Manager ohne
Prognose-EIN ab. Bestehende 16-Zonen-, Neustart-, Prioritäts-, Startberechtigungs-,
HA-/Controller- und 24h-Tests bleiben aktiv. Zur überwachten Abnahme bei geringem
vergleichbarem Bedarf eine vollständige Kette prüfen: kurze Übergaben, gleiche
Heizdauer/Zeitkonten, keine zusätzlichen normalen Starts oder Pumpenunterbrechungen.
Danach Prioritäten und Randbedingungen getrennt prüfen. Helper-Kanten sind keine
physischen Ventilrückmeldungen. Version 9 bleibt zum neuen Store kompatibel;
vor Rückkehr zu Version 8/Original-PR gelten die verlinkten Migrationshinweise.
