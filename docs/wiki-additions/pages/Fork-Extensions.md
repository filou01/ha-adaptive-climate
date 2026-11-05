# Fork extensions / Fork-Erweiterungen

[English](#english) · [Deutsch](#deutsch)

## English

This is the documentation entry point for the optional extensions in
`filou01/ha-adaptive-climate`, development branch `codex/pump-aware-pwm`.
Current software release: **[v0.67.1-pwm.8](https://github.com/filou01/ha-adaptive-climate/releases/tag/v0.67.1-pwm.8)**.
These features are a fork preview, not a claim that the upstream `main` or its
published releases contain the same implementation. The domain remains
`adaptive_climate`; do not install two copies of that domain.

### Read first

| Topic | Documentation |
| --- | --- |
| Configuration, minimal/maximal strategy, compatibility, installation and rollback | [User guide](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/pump-aware-pwm.md#english) |
| Current handover repair, diagnostics and automated/supervised test plans | [Preview 8 report](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/pwm-runtime-handovers.md#english) |
| Current evidence, startup-only live check and remaining validation | [Validation status](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/extension-validation.md#english) |
| Helper-to-relay topology and observation boundary | [input_boolean outputs](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/input-boolean-pwm.md#english) |
| Budget recovery and first-upgrade limitations | [Restart journals](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/pwm-restart-safety.md#english) |
| Ordinary start limits versus genuine priority demand | [Start entitlement](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/pwm-ordinary-starts.md#english) |

### What the extensions do

The opt-in coordinator shifts genuine effective HEAT PWM pulses across zones
sharing one electrically OR-controlled pump. `minimal` first reduces avoidable
group starts, then favors short handovers and solo operation of the highest-
weight zone. It intentionally accepts longer pump energized time. `maximal`
concentrates ordinary pulses and can trade more starts for less energized time.
Neither mode invents heat, owns the pump relay, models physical hydraulic flow
or bypasses minimum switching times. Eligible real target changes/OFF→HEAT
retain immediate response; ordinary PID ticks are not priority events.

| Introduced | Extension and reference |
| --- | --- |
| Preview 1 | Optional coordination, effective pulse reservations, observed-time accounting and serialized actuation; [historical verification](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/architecture/pump-aware-pwm-verification.md#english) |
| Preview 2 | Narrow learning-cycle/settling and PID-diagnostic fixes, durable adjustment-cycle counter; [scope and unresolved maintenance case](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/learning-hotfixes.md#english) |
| Preview 3 | Serialized shared store startup and single learning-window discovery; [startup fix](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/learning-startup-fix.md#english) |
| Preview 4 | Mixed `switch`/`input_boolean` output support; [proxy limits](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/input-boolean-pwm.md#english) |
| Preview 5 | Event-loop-safe timer and state callbacks; [callback fix and separate dt warning](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/pwm-callback-safety.md#english) |
| Preview 6 | Durable PWM budgets, priority deadlines and minimum-time recovery; [journals](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/pwm-restart-safety.md#english) |
| Preview 7 | One ordinary start per zone/group-origin epoch; [entitlement](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/pwm-ordinary-starts.md#english) |
| Preview 8 | Executable minimal handovers using remaining budgets and switching bounds; [current repair](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/pwm-runtime-handovers.md#english) |

Learning/startup fixes also apply when coordination is disabled. Disabling
coordination restores independent output scheduling, not older learning code.
The broader maintenance-learning problem and the PID outside/wind-term switch
near target are not redesigned by these releases. No learning reset is required.

### Evidence and historical records

Each own extension page has English and German sections. Code identifiers,
configuration examples, equations, immutable commit/CI references and original
numeric evidence tables are shared technical records; a translation does not
claim a new test run. Release-specific numbers stay attached to their original
source revision. Current evidence is in [Validation status](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/extension-validation.md#english).

The [original safety review](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/architecture/pump-aware-pwm-safety-review.md#english)
and [overlap-policy decision](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/architecture/pump-aware-pwm-overlap-policy.md#english)
are historical documents. Their original “not implemented”/“unsupported schema”
statements are not current setup instructions. The
[combined PR description](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/architecture/pump-aware-pwm-pr.md#english) is a draft,
not an opened upstream pull request. Private installation traces are not
included in this public documentation.

Original project pages retain English additions. Prepared English additions
for the upstream Wiki are included in this release's documentation bundle;
their presence in the fork must not be confused with upstream acceptance.
See the [Wiki patch, proposed pages and publication status](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/wiki-additions/README.md#english).
Documentation updates are associated with the existing preview release through
its notes and attachments; the installed software tag is not moved.

## Deutsch

Dies ist der Einstieg zu den optionalen Erweiterungen in
`filou01/ha-adaptive-climate`, Entwicklungsbranch `codex/pump-aware-pwm`.
Aktuelle Softwareversion:
**[v0.67.1-pwm.8](https://github.com/filou01/ha-adaptive-climate/releases/tag/v0.67.1-pwm.8)**.
Es handelt sich um eine Fork-Vorabversion. Damit wird nicht behauptet, dass
Upstream-`main` oder dessen Releases dieselben Funktionen enthalten. Die Domain
bleibt `adaptive_climate`; nicht zwei Kopien derselben Domain installieren.

### Zuerst lesen

| Thema | Dokumentation |
| --- | --- |
| Konfiguration, Strategieauswahl, Kompatibilität, Installation und Rückkehr | [Benutzeranleitung](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/pump-aware-pwm.md#deutsch) |
| Aktuelle Übergabekorrektur, Diagnose und automatisierter/überwachter Testplan | [Preview-8-Bericht](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/pwm-runtime-handovers.md#deutsch) |
| Aktuelle Nachweise, begrenzte HA-Startprüfung und offene Validierung | [Prüfstatus](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/extension-validation.md#deutsch) |
| Helfer mit nachgelagertem Relais und Beobachtungsgrenze | [input_boolean-Ausgänge](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/input-boolean-pwm.md#deutsch) |
| Budget-Wiederherstellung und Grenzen der ersten Umstellung | [Neustartjournale](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/pwm-restart-safety.md#deutsch) |
| Gewöhnliche Startbegrenzung und echte Sofortanforderungen | [Startberechtigung](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/pwm-ordinary-starts.md#deutsch) |

### Zweck der Erweiterungen

Die ausdrücklich aktivierte Koordination verschiebt echte wirksame HEAT-
PWM-Pulse von Zonen an einer gemeinsam elektrisch ODER-gesteuerten Pumpe.
`minimal` reduziert zuerst vermeidbare gemeinsame Starts und bevorzugt danach
kurze Übergaben sowie Alleinlauf der höher gewichteten Zone. Längere
Pumpenlaufzeit wird bewusst akzeptiert. `maximal` bündelt gewöhnliche Pulse
und kann kürzere Laufzeit gegen mehr Starts tauschen. Beide Strategien erzeugen
keine zusätzliche Wärme, schalten nicht direkt das Pumpenrelais, modellieren
keinen physischen Durchfluss und umgehen keine Mindestzeiten. Echte zulässige
Zielwechsel und OFF→HEAT reagieren weiterhin sofort; normale PID-Updates sind
keine Prioritätsereignisse.

| Seit | Erweiterung und Verweis |
| --- | --- |
| Preview 1 | Optionale Koordination, effektive Reservierung, beobachtete Zeitbilanz und serialisierte Aktuation; [historischer Nachweis](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/architecture/pump-aware-pwm-verification.md#deutsch) |
| Preview 2 | Enger Lernzyklus-/Settling- und PID-Diagnosefix, dauerhafter Anpassungszähler; [Grenzen und offener Maintenance-Fall](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/learning-hotfixes.md#deutsch) |
| Preview 3 | Serialisierter gemeinsamer Store-Start und einmalige Learning-Window-Entdeckung; [Startkorrektur](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/learning-startup-fix.md#deutsch) |
| Preview 4 | Gemischte Switch-/Helfergruppen; [Beobachtungsgrenze](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/input-boolean-pwm.md#deutsch) |
| Preview 5 | HA-konforme Event-Loop-Callbacks; [Korrektur und separate dt-Warnung](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/pwm-callback-safety.md#deutsch) |
| Preview 6 | Dauerhafte PWM-Budgets, Prioritätsfristen und Mindestzeit-Wiederherstellung; [Journale](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/pwm-restart-safety.md#deutsch) |
| Preview 7 | Eine gewöhnliche Startfreigabe je Zone und Gruppenepoche; [Startberechtigung](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/pwm-ordinary-starts.md#deutsch) |
| Preview 8 | Ausführbare minimale Übergaben aus Restbudgets und Schaltgrenzen; [aktuelle Korrektur](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/pwm-runtime-handovers.md#deutsch) |

Lern-/Startkorrekturen gelten auch bei deaktivierter Koordination. Deren
Deaktivierung stellt unabhängige Ausgangsplanung her, nicht den alten
Lerncode. Der größere Maintenance-Lernfall und das Umschalten des PID-
Außen-/Windanteils nahe Soll werden nicht neu entworfen. Kein Lernreset ist nötig.

### Nachweise und historische Dokumente

Jede eigene Erweiterungsseite hat einen englischen und deutschen Abschnitt.
Kennungen, Konfigurationsbeispiele, Formeln, unveränderliche Commit-/CI-Verweise
und ursprüngliche Messwerttabellen sind gemeinsame technische Nachweise. Eine
Übersetzung stellt keinen neuen Testlauf dar. Versionsbezogene Zahlen bleiben
dem damaligen Quellstand zugeordnet. Aktuelles steht im
[Prüfstatus](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/extension-validation.md#deutsch).

Die [erste Sicherheitsprüfung](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/architecture/pump-aware-pwm-safety-review.md#deutsch)
und die [Strategieentscheidung](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/architecture/pump-aware-pwm-overlap-policy.md#deutsch)
sind historisch. Ihre Aussagen „noch nicht implementiert“ oder „Schema nicht
unterstützt“ sind keine heutige Installationsanweisung. Die
[zusammengefasste PR-Beschreibung](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/architecture/pump-aware-pwm-pr.md#deutsch)
ist ein Entwurf, kein eröffneter Upstream-PR. Private Anlagenverläufe werden
nicht in dieser öffentlichen Doku veröffentlicht.

Ergänzungen an Originalseiten bleiben englisch. Vorbereitete englische
Ergänzungen für das Original-Wiki liegen im Dokumentationspaket dieses Releases;
das bedeutet noch keine Annahme durch Upstream. Dokuänderungen werden über
Notizen und Anhänge dem bestehenden Preview-Release zugeordnet. Der bereits
installierte Software-Tag wird nicht verschoben.
Details stehen unter [Wiki-Patch, Vorschauseiten und Veröffentlichungsstatus](https://github.com/filou01/ha-adaptive-climate/blob/codex/pump-aware-pwm/docs/wiki-additions/README.md#deutsch).
