# Upstream Wiki additions / Ergänzungen für das Original-Wiki

[English](#english) · [Deutsch](#deutsch) · [Extension index](../fork-extensions.md)

## English

These are prepared documentation changes for
`https://github.com/afewyards/ha-adaptive-climate.wiki.git`, not an accepted or
published upstream change. On 2026-11-05 GitHub rejected the authenticated
`filou01` push dry-run with **403 / permission denied**. No upstream Wiki page
was changed and no pull request, issue or message was sent to its maintainer.

The patch is based on Wiki commit
`4646116d51c573edd07db523de01dd5d8918475e`. It adds English-only, explicitly
fork-scoped information to eight existing pages:

- Home
- Installation & Setup
- Configuration Reference
- Multi-Zone Coordination
- Sensors & Monitoring
- Troubleshooting
- Adaptive Learning
- Development

It also adds one own bilingual `Fork-Extensions` portal. All original page
content is preserved; only marked fork-preview sections are inserted. Preview
configuration is never represented as an upstream release capability.

The [complete patch](upstream-wiki.patch) and [renderable proposed pages](pages/Home.md)
are committed with the fork and included in the preview-8 documentation asset.
All eight page previews are in `pages/`; the new portal is
[Fork-Extensions](pages/Fork-Extensions.md). These are review copies, not a live
upstream Wiki. Existing Wiki-style extensionless links refer to the live Wiki;
use the directory listing to navigate these local preview copies.

A maintainer with Wiki write access can review and apply it in a clean clone:

```text
git clone https://github.com/afewyards/ha-adaptive-climate.wiki.git
cd ha-adaptive-climate.wiki
git apply --check /path/to/upstream-wiki.patch
git apply /path/to/upstream-wiki.patch
git diff --check
```

Review the diff and current upstream state before committing/pushing. If the
Wiki has changed since the stated base, reconcile the additions with that
new state instead of overwriting other edits. No force push is needed.
The patch was checked against the exact recorded base. Publication still
requires upstream Wiki write access; attaching it to a fork release does not
grant that access or imply upstream approval.

## Deutsch

Dies sind vorbereitete Ergänzungen für das Original-Wiki
`https://github.com/afewyards/ha-adaptive-climate.wiki.git`, keine dort bereits
angenommenen oder veröffentlichten Änderungen. Am 05.11.2026 wies GitHub den
angemeldeten Push-Dry-run von `filou01` mit **403 / fehlender Schreibberechtigung**
zurück. Es wurde keine Original-Wikiseite geändert und weder PR noch Issue oder
Nachricht an den Hersteller gesendet.

Grundlage ist Wiki-Commit
`4646116d51c573edd07db523de01dd5d8918475e`. Acht vorhandene Seiten erhalten
ausschließlich englische, ausdrücklich als Fork-Preview markierte Ergänzungen:
Startseite, Installation, Konfigurationsreferenz, Mehrzonenkoordination,
Sensoren/Monitoring, Fehlerdiagnose, adaptives Lernen und Entwicklung. Eine
eigene Seite `Fork-Extensions` dient als zweisprachiger Einstieg. Der bestehende
Originalinhalt bleibt erhalten. Preview-YAML wird nicht als upstreamfähige
Konfiguration dargestellt.

Der [vollständige Patch](upstream-wiki.patch) und die
[lesbaren Vorschauseiten](pages/Home.md) liegen im Fork und im Doku-Anhang des
Preview-8-Releases. Alle Vorschauen stehen unter `pages/`, einschließlich des
[zweisprachigen Portals](pages/Fork-Extensions.md). Es sind Prüfkopien, kein
veröffentlichtes Original-Wiki. Bestehende Wiki-Links ohne Dateiendung zeigen
auf das Live-Wiki; für lokale Vorschauen die Verzeichnisansicht verwenden.

Ein Maintainer mit Wiki-Schreibrecht kann die oben gezeigten Befehle in einem
sauberen Wiki-Checkout ausführen. Zuerst Patch und aktuellen Stand prüfen.
Bei Änderungen seit dem angegebenen Basiscommit die Ergänzungen sorgfältig
übernehmen, ohne fremde Bearbeitungen zu überschreiben. Force-Push ist nicht
erforderlich. Der Patch wurde gegen die genannte Basis geprüft. Seine Aufnahme
in den Fork oder Release-Anhang ersetzt weder Schreibrecht noch Upstream-Freigabe.
