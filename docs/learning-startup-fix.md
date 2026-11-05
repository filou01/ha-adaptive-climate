# Shared learning startup fix — preview 3

[English](#english) · [Deutsch](#deutsch) · [Documentation index / Doku-Einstieg](fork-extensions.md)

> **Scope / Geltungsbereich:** Historical release/design record; use the [current documentation index](fork-extensions.md) for preview 8. Historischer Versions-/Designbericht; aktuelle Bedienung und Nachweise stehen im Erweiterungsindex. Original test tables and commit/CI references apply to both language sections and retain their original revision context.

## English

`v0.67.1-pwm.3` fixes the concurrent initialization that can produce:

```text
Platform adaptive_climate does not generate unique IDs.
ID adaptive_climate_learning_window already exists
```

Multiple zone platform setups could pass the missing-store check before any
finished awaiting storage. Each could create its own `LearningDataStore` and
request the same system-wide number entity. Home Assistant rejects the duplicate
entity, but merely hiding that warning would leave the shared-storage race.
Actual loss of the user's saved learning data has not been established.

### Change

One per-HA-domain `asyncio.Lock` is created before the first await. Each zone
rechecks the singleton under this lock. Storage load, manifold restoration and
water-temperature restoration finish before the store is published and the
number platform is requested. Waiting zones then use that same store and restore
their own saved learner data. Failure or cancellation releases the lock without
publishing the incomplete store, allowing a later setup to retry.

The existing unique ID and entity identity are preserved. There is no storage
schema change, learning reset, PID adjustment, heater command or PWM-planner
change in this fix. Both earlier learning hotfixes remain included, with their
[documented scope and limitations](learning-hotfixes.md). Coordination remains
disabled by default; minimal/maximal overlap configuration is unchanged.

### Verification

Source/test commit: `3ea5792d12990c1347b73f094a49e2450cf8e7f8`.
Only documentation is added after this tested commit.

Six new deterministic regressions exercise real zone platform setup with mocked
HA boundaries: four parallel zones blocked during each of storage, manifold or
water-temperature loading; storage/restoration failures followed by retry; and
cancellation with a waiting zone. They verify one successful store initialization,
one number discovery, shared restoration once and per-zone learner restoration.

| Check | Result |
| --- | --- |
| Targeted startup/setup/manifold/water-persistence tests (Windows) | 44 passed |
| Full Linux Python 3.11.18 suite | 3555 passed, 11 skipped; exit 0 |
| Full Linux Python 3.12.3 suite | 3555 passed, 11 skipped; exit 0 |
| Ruff check / format | PASS; 250 files formatted |
| Pyright source | PASS; 0 errors |
| GitHub Linux 3.11/3.12 full tests, lint, format, types | [All check steps PASS; workflow finalization incomplete during release preparation](https://github.com/filou01/ha-adaptive-climate/actions/runs/41876756134) |
| HACS | [PASS](https://github.com/filou01/ha-adaptive-climate/actions/runs/41876756475) |
| hassfest | [PASS](https://github.com/filou01/ha-adaptive-climate/actions/runs/41876756278) |

GitHub recorded every check and cleanup step as successful for both Python
versions, but left the 3.12 job in `in_progress` after its `Complete job` step.
This report does not claim a completed green workflow. Both independent local
Linux runs exited successfully.

The three parallel-start tests also fail against the prior `.2` setup function:
storage loading constructs four instances instead of one; manifold/water
restoration exposes the store before completion. The working tree was not
reverted for this in-memory reproduction.

The full suite includes the existing eight deterministic 24-hour PWM replays;
their assumptions remain described in the [PWM verification report](architecture/pump-aware-pwm-verification.md).

**NOT RUN:** real HA startup/device end-to-end testing, physical pump/relay/flow
tests, supervised 24-hour heating operation, Raspberry Pi performance,
variable maintenance-duty simulation with real actuator timing, full Windows
suite for preview 3, and wiki publication. Preview 2's full Windows run had
eleven existing report-date-format failures; see its hotfix report. Passing
mocked-boundary tests does not establish physical heating behavior.

### Changed files and upgrade

- `custom_components/adaptive_climate/climate_setup.py`: serialize shared startup
  and publish only fully restored storage.
- `tests/test_learning_startup.py`: six regression cases.
- This report, README, prior hotfix report and combined PR draft: release evidence.

Back up integration/configuration/learning storage, select
[`v0.67.1-pwm.3` in the fork's HACS prereleases](https://github.com/filou01/ha-adaptive-climate/releases/tag/v0.67.1-pwm.3)
and restart HA. Do not delete the existing number entity or reset learning data.
No YAML change or standalone patch script is needed. The release tag identifies
the fork preview; the semantic-release-managed manifest remains at `0.67.0`.

Rollback: select the unchanged `v0.67.1-pwm.2` release and restart; that also
restores the startup race. Disabling PWM coordination alone does not undo this
general initialization fix. Retain your backup for rollback to older upstream
versions as described in the earlier hotfix report. No upstream PR is opened.

## Deutsch

### Ursache und Korrektur

Preview 3 beseitigt parallele Initialisierung des gemeinsamen Lernspeichers.
Mehrere Zonen konnten gleichzeitig einen noch fehlenden Store feststellen,
je einen eigenen `LearningDataStore` erzeugen und dieselbe globale Number-
Entity entdecken lassen. HA meldete dann die doppelte ID
`adaptive_climate_learning_window`. Ein tatsächlicher Verlust gespeicherter
Lerndaten wurde durch diese Warnung allein nicht nachgewiesen.

Ein gemeinsames `asyncio.Lock` wird vor dem ersten Await erstellt. Unter diesem
Lock wird erneut auf den Singleton geprüft. Erst nach abgeschlossenem Laden
von Speicher, Verteiler- und Wassertemperaturzuständen wird der Store publiziert
und die Number-Plattform angefordert. Wartende Zonen verwenden dieselbe Instanz
und stellen ihre eigenen Lerndaten wieder her. Fehler und Abbruch geben das
Lock frei, ohne einen unvollständigen Store zu veröffentlichen; spätere Aufrufe
dürfen erneut versuchen zu laden.

Unique-ID und Entity-Identität bleiben erhalten. Es gibt keinen Schemawechsel,
Lernreset, PID-Eingriff, Heizbefehl oder geänderten PWM-Planer. Die beiden
vorherigen Lernkorrekturen bleiben mit ihren dokumentierten Grenzen enthalten.

### Historische Nachweise

Geprüfter Quellstand: `3ea5792d12990c1347b73f094a49e2450cf8e7f8`.
Sechs neue deterministische Tests prüfen parallele Zonen während Store-,
Verteiler- und Wassertemperatur-Laden, Fehler mit erneutem Versuch sowie Abbruch
mit wartender Zone. Erwartet werden genau eine gemeinsame erfolgreiche
Initialisierung, eine Number-Entdeckung und korrekte zonenweise Wiederherstellung.
Die drei Parallelstart-Reproduktionen scheiterten auch gegen den vorherigen
Preview-2-Setupcode, ohne den Arbeitsbaum dafür zurückzusetzen.

Die Originaltabelle im englischen Teil gehört zu diesem Quellstand: 44 gezielte
Windows-Tests, Linux 3.11/3.12 jeweils 3555 bestanden und 11 übersprungen,
Ruff/Format/Pyright erfolgreich. HACS und hassfest waren erfolgreich. Bei der
damaligen GitHub-Matrix waren alle Prüf- und Cleanup-Schritte erfolgreich, der
3.12-Job blieb jedoch nach `Complete job` als laufend markiert. Der historische
Bericht behauptet deshalb ausdrücklich keinen abgeschlossenen grünen Workflow.
Die beiden unabhängigen lokalen Linux-Läufe waren erfolgreich.

Die acht damaligen PWM-Tagesmodelle bleiben Modellversuche. Reale HA-/Geräte-
Prüfung, Pumpen-/Relais-/Durchflussmessung, überwachter Tagesbetrieb,
Raspberry-Pi-Messungen, variabler Maintenance-Versuch mit echten Aktorzeiten,
vollständige Windows-Suite für Preview 3 und Wiki-Veröffentlichung wurden damals
nicht durchgeführt. Preview 2 hatte elf bestehende Windows-Datumsformatfehler.

### Dateien, Installation und Rollback

Geändert wurden vor allem `climate_setup.py` und `tests/test_learning_startup.py`;
die vollständigen Nachweise und Links stehen im englischen Teil. Vor dem
Upgrade Integration, Konfiguration und Lernspeicher sichern, in HACS die
Fork-Vorabversion wählen und HA neu starten. Die bestehende Number-Entity nicht
löschen. Weder YAML-Änderung noch Zusatzskript oder Lernreset ist erforderlich.

Preview 2 wieder zu installieren und neu zu starten bringt auch das Startrennen
zurück. Nur die PWM-Koordination zu deaktivieren nimmt diese allgemeine
Initialisierungskorrektur nicht zurück. Für ältere Upstream-Versionen die
Speicherhinweise des Hotfix-Berichts beachten. Der Fork-Tag bezeichnet die
Preview; der Manifestwert bleibt `0.67.0`.
