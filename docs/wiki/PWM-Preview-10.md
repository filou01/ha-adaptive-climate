# PWM Preview 10 / PWM-Vorabversion 10

## English

This is an experimental fork test version on `test/pwm-storage-hydraulics`.
Its joint handover repair can replace unnecessary parallel ordinary pulses
with a chain while retaining the pump-start objective, heat grants and timing
constraints. Active, priority and forecast windows remain fixed. A maximum of
256 additional joint proposals bounds runtime work; global optimality is not claimed.

Explicitly configure `handover_overlap_seconds: 120` for two-minute handovers;
the compatible default remains 240s. Follow the release installation and migration
instructions before changing versions. Physical valve and pump behavior still
requires supervised verification.

[Design and acceptance plan](https://github.com/filou01/ha-adaptive-climate/blob/test/pwm-storage-hydraulics/docs/pwm-joint-handovers.md)
· [Test release](https://github.com/filou01/ha-adaptive-climate/releases/tag/v0.67.1-pwm.10)

## Deutsch

Dies ist eine experimentelle eigene Testversion im Zweig
`test/pwm-storage-hydraulics`. Gemeinsame Verschiebungen können unnötige parallele
Normalimpulse durch eine Kette ersetzen. Pumpenstartziel, Wärmebudgets und
Zeitgrenzen bleiben erhalten; laufende, priorisierte und Prognosefenster bleiben
fest. Höchstens 256 zusätzliche Vorschläge begrenzen die Rechenarbeit.

Für zwei Minuten ausdrücklich `handover_overlap_seconds: 120` setzen; der
kompatible Standard bleibt 240s. Vor Versionswechsel die Installations- und
Migrationshinweise des Releases lesen und anschließend überwacht prüfen.
Die Links oben führen zur zweisprachigen Beschreibung und Testversion.
