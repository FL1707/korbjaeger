# Korbjäger

Basketball-News-App für Kinder (NBA, BBL, Euroleague, Champions League, Nationalmannschaft), veröffentlicht über GitHub Pages.

- `index.html`: die komplette App (HTML, CSS, JS)
- `data.json`: alle Inhalte; wird täglich um 6:00 und 16:00 Uhr von einer geplanten Claude-Code-Aufgabe neu geschrieben und per `git push` veröffentlicht
- `archiv.json`: ältere Artikel für das Liga-Menü
- `nba-stats.json`: NBA-Spielerstatistik (Quelle NBA.com), erzeugt mit `werkzeuge/nba-stats.ps1` aus der im Browser ausgelesenen Tabelle
- `apple-touch-icon.png`: Symbol für den iPad-Home-Bildschirm

Alle Bilder sind selbst gezeichnete SVG-Motive; es werden keine Pressefotos oder echten Team-Logos verwendet.
