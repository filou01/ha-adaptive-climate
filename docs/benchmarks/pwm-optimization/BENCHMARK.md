# PWM optimization benchmark / PWM-Optimierungsbenchmark

Controlled synthetic 24h replay / Kontrollierte synthetische 24h-Wiedergabe.

| Trace | Writes before → after | Bytes before → after | Pump starts | Delivery deviation |
| --- | ---: | ---: | ---: | ---: |
| continuous-60-maximal | 5793 → 1453 | 113185634 → 4845652 | 1 | 0 s |
| continuous-60-minimal | 5816 → 1476 | 113625368 → 4919252 | 1 | 0 s |
| idle-60-maximal | 5785 → 4 | 112333130 → 22704 | 0 | 0 s |
| idle-60-minimal | 5785 → 4 | 112333130 → 22704 | 0 | 0 s |
| noise-10-maximal | 35013 → 20002 | 688025572 → 69303952 | 24 | 0 s |
| noise-10-minimal | 35110 → 23513 | 691528424 → 82105128 | 24 | 0 s |
| priority-60-maximal | 6249 → 619 | 121889369 → 2060818 | 24 | 0 s |
| priority-60-minimal | 6331 → 723 | 123471428 → 2395998 | 24 | 0 s |
| steady-10-maximal | 35049 → 2051 | 682578851 → 6745663 | 24 | 0 s |
| steady-10-minimal | 35139 → 3245 | 684541462 → 10652467 | 24 | 0 s |
| steady-60-maximal | 6249 → 611 | 121706623 → 2016726 | 24 | 0 s |
| steady-60-minimal | 6339 → 725 | 123493874 → 2387060 | 24 | 0 s |

Exact transitions, signed ledgers and hydraulic observations are identical in every pair.
Alle Ausgangswechsel, Zeitkonten und hydraulischen Beobachtungen sind je Vergleich identisch.

See the CSV/JSON files for critical/noncritical writes, timings, per-zone scores, solo time and overlap.
CSV/JSON enthalten Schreibzahlen, Laufzeiten, Zonen-Scores, Alleinlauf und Überlappung.

The scores describe weighted output-state competition, not measured flow or PID improvement.
Die Scores beschreiben gewichtete Ausgangs-Konkurrenz, keinen gemessenen Durchfluss oder PID-Fortschritt.
