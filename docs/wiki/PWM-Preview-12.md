# PWM preview 12: start spacing / Startabstände

## English

### Two corrections

Preview 11 limited ordinary starts by group-origin epoch. A late pulse in one
epoch and an early pulse in the next could therefore start much less than one
PWM period apart. This satisfied the old epoch invariant; an existing regression
even explicitly allowed a next-epoch start without a rolling cooldown. It did
not enforce the intended protection against clustered ordinary starts.

Preview 12 tightens that policy: an ordinary OFF→ON transition must be at least
one configured PWM period after that zone's last observed ON, including a prior
priority start. This applies to both overlap strategies. It is a per-zone bound,
not a promise of one shared-pump start per hour. Existing epoch allowances remain
in force as well. Genuine target/mode priority requests and continuous demand
can bypass the ordinary spacing rule, while minimum OFF still applies.

The bound participates in executable planning, advisory forecasts, command
scheduling and the final pre-command check after awaited persistence. Merely
crossing an epoch boundary no longer removes it. Existing heat grants and signed
accounting remain authoritative; the guard does not create heat or cut an active
pulse. It can delay ordinary demand even when the configured deferral deadline
is earlier, just as a binding minimum OFF time can do. A valid neighboring chain
still wins among plans within these bounds.

Separately, the coordinated adapter did not reset its low-duty accumulator on
zero demand. Its old calculation timestamp could survive the idle interval,
allowing a later small demand to count that whole interval as earned heat. The
independent PWM path already resets both fields for zero demand. The coordinated
path now does the same; on a positive-demand pause it preserves earned credit
but clears the accrual clock, so the pause earns nothing.

### Why previous validation missed this

The earlier checks covered one ordinary start per logical epoch, minimum ON/OFF,
signed heat balances and overlap durations. All of those can pass while two
ordinary ON edges across the epoch boundary are too close together. The
simulation also used a narrowed adapter and did not check accrual across a long
zero-demand gap. A cold scheduler, assumed timing and absent journal state were
documented limitations, but did not compensate for these missing assertions.

The updated regression suite compares observed ON timestamps across boundaries,
not calendar-hour buckets. It covers 30/60/120-minute PWM, both strategies, real
HA adapters for switch/helper outputs, priority and continuous exceptions,
monotonic-reset restart, old-journal upgrade, malformed future timestamps,
zero-demand accrual and paused accrual. Ten selected regressions fail with the
original preview-11 manager and pass with preview 12. A full-day delivery check
now includes an active pulse's remaining credit at the window boundary rather
than silently assuming all spaced pulses finish before the cutoff.

A separate local replay feeds unchanged recorded temperatures, demand, target
and mode values into both actual manager versions and reproduces the production
pattern before the fix. It now asserts elapsed ordinary-start spacing as well
as epoch quotas, minimum times and accounting. Private histories and replay
inputs are deliberately excluded from this repository and release assets.
Measured temperatures stay fixed: this is not a closed-loop prediction of
comfort or energy, and it does not guarantee unchanged delivered time when
recorded demand cancels at a later point in the new schedule.

There is a real tradeoff: forbidding a close ordinary start may prevent joining
another zone's current ON window and increase the number of shared-pump starts.
Report room spacing, group starts, energized duration and per-zone delivery
separately; do not present improved room spacing as guaranteed pump savings.

### Persistence and supervised acceptance

An additive `last_start_at` wall timestamp preserves the last observed ON across
restart; running control uses monotonic time. Old journals use a consistent
pipeline-open timestamp when available, otherwise a conservative upper bound
from the saved epoch. An uncertain pending ON uses recovery time. Thus an
upgrade/recovery may defer an ordinary start for up to one PWM period; it does
not reset learning or replay offline heat. Existing journal readers ignore the
additive field, but downgrading removes this protection.

1. Install fork prerelease `v0.67.1-pwm.12` with the usual backup/OFF-output
   procedure and restart HA. Retain the existing PWM and minimum-time settings.
2. Keep `handover_overlap_seconds: 120` for two-minute handovers (default is
   still 240 seconds). No configuration rewrite or learning reset is needed.
3. Check `pwm_coordination.ordinary_restart_in_seconds` per zone. It counts down
   only the ordinary guard; an eligible priority request may bypass it.
4. Observe several complete PWM periods after the upgrade guard expires. For
   each ordinary start, compare its time with the preceding ON in the same zone.
   Require a full configured period; classify true target/mode/continuous
   exceptions separately. Restart once under supervision to check the guard.
5. Observe zero/low-demand transitions, priority reaction, minimum ON/OFF, signed
   balances, ordinary chain overlap, room temperature and actual group starts.
   A remaining minimum-length pulse is not itself a failure: demand may have
   disappeared after ON, and real minimum ON must still be respected.

Publishing this fork preview does not install it or change production HA.
Upstream PR9 is unchanged. Preview 11 is a compatible journal rollback but
restores the two old behaviors; older preview-8 rollback precautions still apply.

## Deutsch

### Zwei Korrekturen

Version 11 begrenzte normale Starts auf eine gemeinsame logische PWM-Epoche.
Ein später Start vor und ein früher Start nach der Grenze konnten deshalb
deutlich weniger als eine PWM-Periode auseinanderliegen. Das entsprach der
alten geprüften Regel; ein Test erlaubte diesen Fall sogar ausdrücklich.
Die gewünschte Vermeidung gehäufter normaler Starts war damit nicht abgedeckt.

Version 12 verschärft die Regel: Ein normaler AUS→EIN-Übergang liegt mindestens
eine konfigurierte PWM-Periode nach dem letzten beobachteten EIN derselben Zone,
auch nach einem priorisierten EIN. Das gilt für beide Überlappungsstrategien.
Es ist keine Garantie für höchstens einen gemeinsamen Pumpenstart pro Stunde.
Echte Sollwert-/Modus-Prioritäten und kontinuierlicher Bedarf dürfen die normale
Wartezeit umgehen; Mindest-AUS bleibt gültig. Die bisherige Epochenberechtigung
gilt zusätzlich. Der Abstand wird in Planung, Prognose, Timer und direkt vor
dem Befehl nach abgewarteter Speicherung geprüft. Ein früheres Aufschublimit
kann die normale Startbegrenzung ebenso wenig umgehen wie Mindest-AUS.

Zudem blieb bei null Bedarf die alte Zeitbasis der Kleinstlast-Sammlung erhalten.
Beim nächsten kleinen Bedarf konnte die Pause fälschlich als verdiente Heizzeit
zählen. Nun werden bei null Bedarf Guthaben und Zeitbasis wie im unabhängigen
PWM-Pfad zurückgesetzt. Bei einer Pause mit positivem Bedarf bleibt bereits
verdientes Guthaben erhalten; die Pause selbst sammelt keine Heizzeit.

### Warum die bisherigen Tests das nicht zeigten

Geprüft wurden ein normaler Start pro Epoche, Mindestzeiten, Zeitbilanz und
Übergaben. Alle können trotz zu kurzer Startabstände über die Epochen-Grenze
bestehen. Dem vereinfachten Simulationsadapter fehlte zudem eine Prüfung der
Sammlung über lange Nullbedarfsphasen. Dokumentierte Annahmen zu Kaltstart,
Mindestzeiten und unbekanntem Journal ersetzen diese fehlenden Prüfungen nicht.

Die neuen Tests prüfen echte Zeitabstände: 30/60/120 Minuten PWM, beide
Strategien, echte HA-Adapter für Schalter und Helper, Priorität, Dauerbedarf,
Neustart mit zurückgesetzter monotoner Uhr, alte Journale, ungültige Zeitstempel
sowie Nullbedarf und Pause. Zehn ausgewählte Regressionen scheitern am originalen
Version-11-Manager und bestehen mit dem Fix. Ein am Ende des Beobachtungsfensters
noch laufender Impuls wird mit Restguthaben bilanziert, statt abgeschnittene
Beobachtungszeit als fehlende Wärmelieferung zu behandeln.

Der zusätzliche lokale Replay reproduziert das Produktionsmuster mit denselben
gemessenen Temperatur-, Bedarfs-, Sollwert- und Moduswerten in beiden echten
Managerversionen. Er prüft jetzt auch den zeitlichen Startabstand und unterscheidet
berechtigte Ausnahmen. Persönliche Historien und Eingaben werden nicht ins
Repository oder Release hochgeladen. Die Temperaturen bleiben feste Eingaben;
Komfort, Energie und identische Lieferung bei zeitlich veränderten Stornierungen
sind damit nicht vorhergesagt.

Die strengere Raumbegrenzung kann das Anschließen an eine andere aktuell
heizende Zone verhindern und dadurch gemeinsame Pumpenstarts erhöhen. Deshalb
Startabstand pro Raum, Gruppenstarts, Pumpenlaufzeit und Raum-Heizzeiten getrennt
bewerten. Kürzere Parallelität oder größere Raumabstände sind kein pauschaler
Nachweis weniger Pumpenschaltungen.

### Speicher und Abnahme

Das zusätzliche Feld `last_start_at` speichert den beobachteten EIN-Zeitpunkt
neustartfest. Im Betrieb bleibt die Zeitrechnung monoton. Bei alten Journalen
wird ein passender vorhandener Ventil-EIN-Zeitpunkt genutzt, sonst eine sichere
obere Grenze aus gespeicherter Epoche und Speicherzeit. Ungewisses ausstehendes
EIN wird konservativ ab Wiederanlauf gerechnet. Nach Upgrade/Unsicherheit kann
ein normaler Start daher bis zu einer PWM-Periode warten. Kein Lernreset und
keine nachträglich erfundene Heizzeit während Ausfall.

Testversion `v0.67.1-pwm.12` mit Sicherung und sicher gestoppten Zonen installieren,
HA neu starten und die bestehenden Mindestzeiten/PWM-Werte beibehalten. Für zwei
Minuten weiterhin `handover_overlap_seconds: 120` setzen; Standard bleibt 240s.
`pwm_coordination.ordinary_restart_in_seconds` zeigt die normale Restwartezeit.
Nach Ablauf des Upgrade-Schutzes mehrere volle Perioden beobachten und jeden
normalen Start mit dem vorherigen EIN derselben Zone vergleichen. Echte
Prioritäts-/Modus-/Dauerbedarfs-Ausnahmen getrennt markieren. Unter Aufsicht
Neustart, Null-/Kleinstlast, Mindestzeiten, Zeitkonto, Übergaben, Raumtemperaturen
und Gruppenstarts prüfen. Ein Mindestimpuls bleibt bei nachträglich entfallenem
Bedarf zulässig; die reale Mindestlaufzeit darf nicht abgeschnitten werden.

Veröffentlichung installiert oder ändert HA nicht. PR9 bleibt unverändert.
Version 11 ist speicherkompatibel, bringt bei Rückkehr aber beide alten Verhalten
zurück. Für Version 8 gelten weiterhin die älteren Migrationshinweise.
