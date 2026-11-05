# Extension validation / Prüfstatus der Erweiterungen

[English](#english) · [Deutsch](#deutsch) · [Documentation index](fork-extensions.md)

## English

Status date: **2026-11-05**. Software: `v0.67.1-pwm.8`, release commit
`3131ecbc6036eebd6ca8bee9ce8d9f192cec28bc`. Tested source/test commit:
`206ad4f430e5957a68a3cc120f62e539f401896d`. Their source/test trees are identical.
Subsequent documentation commits do not change the installed software.

| Evidence | Result and scope |
| --- | --- |
| Root-cause reproduction before repair | Three new regressions failed on preview 7 |
| New executable handover tests | 37 passed locally; includes switch/input_boolean controller boundaries |
| All `test_pwm*.py` files | 271 passed locally |
| Full Linux Python 3.11 and 3.12 | Each 3719 passed, 11 skipped; six existing marker warnings |
| Ruff / format / Pyright | Passed; 256 files formatted, zero type errors |
| HACS / hassfest | Passed for tested source and release documentation commits |
| Windows full suite | 3707 passed, 11 skipped, 12 failures; unmodified preview 7 has the same twelve failure names in this environment |
| Additional 24h late-demand model + 1800s drain | Group starts 49→25, identical 30000/14400 per-zone electrical seconds, zero ending credit |
| Installed HA startup smoke check | Version 8 loaded; four configured zones active in minimal mode, new runtime diagnostics present, no coordinator fallback or scheduler/storage/actuator errors in the queried integration log |

Windows failures: eleven pre-existing `%b %-d` report formatting failures and
one unchanged real-clock undershoot test that can see zero elapsed time in a
full run; it passed alone. No unrelated report/undershoot fix is included.

Exact-source evidence:
[Linux matrix](https://github.com/filou01/ha-adaptive-climate/actions/runs/41986443641),
[HACS](https://github.com/filou01/ha-adaptive-climate/actions/runs/41986443634),
[hassfest](https://github.com/filou01/ha-adaptive-climate/actions/runs/41986443639).
The release documentation commit also passed
[its matrix](https://github.com/filou01/ha-adaptive-climate/actions/runs/41987572413),
[HACS](https://github.com/filou01/ha-adaptive-climate/actions/runs/41987572439) and
[hassfest](https://github.com/filou01/ha-adaptive-climate/actions/runs/41987572532).

The startup check was read-only and occurred before new heating cycles. Signed
zone ledgers balanced and prior allowances/counters were retained. Outputs were
OFF with temperatures above target; a next evaluation was scheduled. This does
not validate real handovers, delivered heat or pump savings. A contact sensor
was unavailable and the existing dt warning occurred; these are separate
observations, not proof of a scheduler failure or a passed contact-safety test.

**Still not validated:** actual multi-zone handover cycles on the installation,
downstream helper-to-relay behavior, physical pump/flow, supervised 24h heating,
real power failure/OS-cache durability, Raspberry Pi performance, save latency
and SD write volume. Models use declared electrical timing and are not a
hydraulic or thermal-feedback simulation. Start reduction in one model is not
a universal performance guarantee.

Use the [supervised test plan](pwm-runtime-handovers.md#supervised-installation-test-plan)
and compare actual edges, per-zone ON seconds, signed balances, ordinary epoch
quotas, priority latency and room comfort. Keep a backup and record unavoidable
gaps together with changing demand; never add heat just to improve a metric.

## Deutsch

Stand: **05.11.2026**. Software: `v0.67.1-pwm.8`, Release-Commit
`3131ecbc6036eebd6ca8bee9ce8d9f192cec28bc`. Geprüfter Source-/Test-Commit:
`206ad4f430e5957a68a3cc120f62e539f401896d`. Quell- und Testbaum sind identisch.
Spätere Dokucommits ändern die installierte Software nicht.

| Nachweis | Ergebnis und Geltungsbereich |
| --- | --- |
| Reproduktion vor der Übergabekorrektur | Drei neue Regressionstests scheiterten auf Preview 7 |
| Neue Übergabetests | 37 lokal bestanden; echte Switch-/Helfer-Controllergrenzen enthalten |
| Alle `test_pwm*.py` | 271 lokal bestanden |
| Linux 3.11 und 3.12 vollständig | Je 3719 bestanden, 11 übersprungen; sechs bestehende Markerwarnungen |
| Ruff / Format / Pyright | Bestanden; 256 Dateien formatiert, keine Typfehler |
| HACS / hassfest | Für geprüften Source- und Release-Dokucommit bestanden |
| Windows vollständig | 3707 bestanden, 11 übersprungen, zwölf Fehler; unveränderter Vorgänger mit identischen zwölf Fehlernamen |
| Zusätzliches Tagesmodell + 1800s Nachlauf | Starts 49→25, identische 30000/14400 ON-Sekunden je Zone, null Endguthaben |
| Begrenzte Startprüfung in installierter HA-Instanz | Version 8 geladen, vier Zonen aktiv mit minimal, neue Diagnose vorhanden, kein Rückfall oder Scheduler-/Speicher-/Aktorfehler im abgefragten Integrationslog |

Windows: elf alte Berichts-Datumsformatierungen und ein unveränderter Test mit
realer Uhr, der im Vollauf null vergangene Zeit sehen kann; einzeln bestand er.
Diese fremden Berichts-/Undershoot-Ursachen wurden nicht mitgeändert. Die
unveränderlichen CI-Verweise oben gelten für beide Sprachabschnitte.

Die reine Leseprüfung erfolgte nach Installation und Neustart vor neuen
Heizzyklen. Signierte Bilanzen stimmten, frühere Freigaben/Zähler blieben
erhalten. Bei Temperaturen über Soll waren die Ausgänge OFF; der nächste
Abgleich war eingeplant. Das bestätigt keine echten Übergaben, Wärmelieferung
oder Pumpeneinsparung. Ein Kontakt war nicht verfügbar und die bestehende
dt-Warnung trat auf. Das sind getrennte Beobachtungen, kein Beweis für einen
Planerfehler oder eine bestandene Kontaktsicherheitsprüfung.

**Noch offen:** echte Mehrzonen-Übergaben in der Anlage, Helfer-/Relaisübernahme,
physische Pumpe und Durchfluss, überwachter Heiztag, echte Stromausfall-/
OS-Cache-Dauerhaftigkeit sowie Raspberry-Pi-Leistung, Save-Latenz und
SD-Schreibvolumen. Die Modelle sind elektrische Zeitmodelle ohne echte
Hydraulik oder thermische Rückkopplung. Eine Einsparung in einem Modell
garantiert keine entsprechende Einsparung in jeder Anlage.

Den [überwachten Testplan](pwm-runtime-handovers.md#deutsch) verwenden: echte
Kanten, ON-Sekunden je Zone, signierte Bilanz, gewöhnliche Epochenfreigaben,
Prioritätslatenz und Raumkomfort vergleichen. Backup behalten und unvermeidbare
Lücken samt Bedarfsänderung dokumentieren. Keine Wärme nur zur Verbesserung
einer Diagnosezahl erzeugen.
