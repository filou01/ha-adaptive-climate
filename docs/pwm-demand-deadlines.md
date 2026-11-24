# PWM v15 candidate: heat before serialization / Heizbedarf vor Serialisierung

## Deutsch

Dieser Kandidat ändert nur ausführbare Startfenster und Diagnosen. Budgetanker,
Periodenvergabe, v13-Nullbedarfsfix, v14-Startabstand, Prioritätsregeln,
Mindestzeiten, Aktorsteuerung und Journalformat bleiben erhalten.

### Nachgewiesener Fehler in v14

Der zyklische Optimierer kann notwendige zusätzliche Überlappung berechnen.
Die Runtime bewertete danach Pumpenstarts, Übergabequalität und möglichst
geringe Überlappung vor Startpünktlichkeit. Ein bereits freigegebenes positives
Folgebudget durfte innerhalb eines breiten Fensters für eine schönere Kette
nach hinten verschoben werden. Die neue tatsächliche EIN-Flanke wurde korrekt
als nächster v14-Budgetanker gespeichert. Dadurch wanderte der Folgetermin mit.

Die vorherigen Auditoren prüften Bilanz, gewöhnlichen Startabstand, Mindestzeiten,
keine doppelte Gutschrift und keine neue Periode während EIN. Alle Kriterien
konnten trotz verspäteter Lieferung bestehen: bereits vergebene Zeit blieb als
Guthaben sichtbar; später noch nicht vergebene Kalenderperioden tauchten in
keinem dieser Zähler auf. Ein größeres cancelled_balance ist für sich kein
Nachweis verlorener berechtigter Zeit, da auch reguläre PID-Revisionen und
Bedarfswiderrufe dort bilanziert werden.

Ein reproduzierbarer Vier-Raum-Fall mit 1800/1200/900/900 elektrischen Sekunden,
3600 Sekunden Periode, Gewichten 4/1/1/1 und 120 Sekunden Übergabe zeigt im
Original erste Folgeabstände von 4320 Sekunden statt 3600. Bei konstanten
Anforderungen erreicht die Anfangsverschiebung rund 780 Sekunden; bei den
getesteten wechselnden Ausgaben wächst sie weiter. Die bilanzierte Zeit kann
dabei korrekt sein und dennoch zeitlich hinter dem Bedarf zurückliegen.

### Gewählter minimaler Fix

Ein gewöhnlicher Raum mit bereits beobachtetem Start erhält für sein nächstes
ausführbares reserviertes Budget die frühestmögliche sichere Startzeit zugleich
als späteste hydraulisch zulässige Startzeit. Mindest-AUS und v14-Startabstand
bestimmen diese Grenze. Runtime-Reparaturen müssen nötigenfalls mehr Räume
überlappen lassen. Sie dürfen die freigegebene Folgeanforderung nicht für
Pumpen-/Gewichtspräferenzen verschieben.

Die erste Einordnung eines Raums ohne beobachtete Startreferenz behält bei
Unterlast das bisherige begrenzte Übergabefenster. Bei Überlast bildet dagegen
die zyklische Phase die späteste erste Platzierung: Die Runtime darf die vom
zyklischen Plan bereits notwendige Überlappung nicht wieder herausserialisieren.
Damit bleiben nützliche erste Übergaben bei Unterlast,
bekannte physikalische Mindest-AUS-Verschiebungen und zurückgezogene ungestartete
Anforderungen geschützt. Bei stabilen Folgebudgets bleiben dann die erarbeiteten
Phasen erhalten. Eine laufende Anforderung darf über eine Gruppengrenze reichen;
ein zweites normales Periodenbudget wird weiterhin nicht angehängt.

Eine Änderung der globalen Budgetzeitbasis ist für die bestätigte Fehlerklasse
nicht nötig: Die neuen Mehrperiodentests bestehen mit der Runtime-Korrektur,
während derselbe v14-Budgetanker unverändert bleibt. Ein Umbau dieses Ankers
würde zusätzlich Journalmigration, Startquoten und Recovery betreffen und wird
deshalb in diesem Kandidaten nicht vorgenommen. Bereits geerbte Phasen werden
nicht rückwirkend aufgeholt; neue reine Koordinationsverzögerungen entfallen.

### Diagnose und Grenzen

* runtime_deadline_policy = heat_before_serialization.
* scheduled_start_delay_seconds: geplanter Aufschub eines positiven ungestarteten
  Budgets gegenüber der aktuellen Mindestzeit-/Startabstandsgrenze.
* start_delay_reason trennt Mindest-AUS, Startabstand, fehlende Berechtigung,
  vorzeichenbehaftete Bilanz, erste Übergabe und ausführbares Budget.
* overlap_required_seconds: mindestens notwendige kombinierte Überlappung aus
  der Summe aktuell berechtigter elektrischer Zuteilungen minus Periode.
* projected_combined_overlap_seconds: kombinierte Überlappung des zyklischen
  Phasenmodells für aktuell berechtigte Räume. Kein gemessener hydraulischer
  Wert und keine paarweise gewichtete Überlappung.

Die Diagnose wird berechnet, nicht zusätzlich persistiert. Bereits vorhandene
Ledger- und Hydraulikwerte behalten ihre Bedeutung. Physikalische Mindestzeiten,
voller Dauerbedarf, Kleinstlast, wegfallender Bedarf, nicht verfügbare Aktoren,
HA-Unterbrechungen und unzureichend beobachtete Recovery-Zeiten bleiben Ausnahmen.

Mehr Überlappung kann hydraulische Scores verschlechtern oder Pumpenstarts
erhöhen. Dies ist nach der neuen Priorität besser als eine nur hydraulisch
begründete spätere Wärmeanforderung. Die Gewichte bleiben für erlaubte erste
Einordnungen und die Bewertung freier Möglichkeiten aktiv; sie dürfen eine
verbindliche Wärmefrist nicht überschreiben. Kein Nachweis unveränderter
Raumtemperatur oder gleichmäßiger physischer Durchflüsse folgt allein aus
elektrischer Zeitlieferung.

### Regressionen und Replay

test_pwm_budget_deadlines.py prüft 30/60/120 Minuten, vier überlastete Räume,
Mindestzeiten, mehrere Perioden, driftfreie Startabstände, vollständige Zeitbudgets,
wechselnde Ausgaben und den weiterhin getrennten späten Einzelraumimpuls.
Der opt-in Replay-Auditor erfasst zusätzlich late_recurring_budget_starts:
Ein erstmals ausführbares positives Folgebudget erhält eine unabhängige,
unveränderliche sichere Frist. Eine spätere tatsächliche EIN-Flanke wird samt
Verzögerung gemeldet. Echte Prioritäten, kontinuierlicher Bedarf und fehlende
gültige Reservierungen werden dabei getrennt behandelt.

Historische Aufzeichnungen bleiben externe private Eingaben. Replays ohne
vollständigen Journalzustand sind bedingte Open-Loop-Vergleiche; Recorder-Lücken
dürfen nicht durch erfundene PID- oder Aktorereignisse geschlossen werden.

## English

This candidate changes runtime start bounds and diagnostics, keeping the v14
observed-start budget anchor, grant accounting, spacing, priority, actuator and
journal paths. The v14 runtime could delay a valid recurring reservation to
reduce pump starts or excess overlap. The delayed observed ON then moved the
next budget anchor. Ledger and minimum-spacing checks did not detect lateness.

Once a room has an observed cadence and a positive executable ordinary budget,
the safe spacing/minimum-OFF bound is now also its hydraulic latest start.
Additional concurrency wins over postponing requested heat. Initial overloaded
placements also retain the cyclic phase deadline and its required overlap.
Initial rooms under capacity keep their bounded handover window, preserving useful first-placement and
withdrawal behavior. Continuous demand, low duty and real physical limits keep
their exceptions. No ordinary period is appended to a running pulse.

New multicycle overload regressions pass without redesigning the anchor or
migrating storage. The recorded-input auditor additionally reports recurring
reservations started after their independently recorded safe deadline. New
computed diagnostics distinguish physical bounds, initial handovers, signed
balances and executable demand, and expose required versus projected combined
cyclic overlap. No additional periodic persistence is introduced.

Higher overlap or pump-start counts can be necessary to meet the heat-first
priority. Electrical replay is not evidence of unchanged thermal comfort or
physical flow balance. Missing recorder/journal/actuator data remain explicit.
