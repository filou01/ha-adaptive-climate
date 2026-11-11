# Wiki update / Wiki-Aktualisierung

## English

`pwm-coordination.patch` appends an English section to the existing upstream
`Multi-Zone-Coordination` wiki page. It does not replace the page. The separate
upstream wiki repository is not writable with this contributor account (HTTP 403).
A maintainer can apply `git apply --check pwm-coordination.patch` and then
`git apply pwm-coordination.patch` in a current wiki checkout after reviewing the
patch context. Publish alongside the feature merge; links target upstream main.

## Deutsch

Der Patch ergänzt die originale Wiki-Seite auf Englisch. Er ersetzt sie nicht.
Das separate Hauptprojekt-Wiki ist für das Beitragskonto nicht schreibbar (HTTP
403). Ein Maintainer kann den Patch im aktuellen Wiki-Checkout mit `git apply
--check` prüfen, anwenden und zusammen mit dem Feature veröffentlichen.
