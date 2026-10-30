#!/usr/bin/env python3
# Holt die BBL-Spielerstatistik der laufenden Saison (Hauptrunde, Durchschnitt pro Spiel) von der öffentlichen Seite
# https://easycredit-bbl.de/statistiken/spieler und schreibt bbl-stats.json im Format der App (gleiche Spalten wie nba-stats.json,
# dazu "eff" = Effizienz). Die Seite bettet ihre Daten als JSON (__NEXT_DATA__) ein; ein Browser ist nicht nötig.
# Die BBL liefert dort kein Alter, keine Siege/Niederlagen je Spieler und keine Nationalität: diese Spalten bleiben null.
# Aufruf: python3 werkzeuge/bbl-stats.py                (Seite abrufen und bbl-stats.json schreiben)
#         python3 werkzeuge/bbl-stats.py --html datei   (zum Testen eine gespeicherte Seite verwenden)
import argparse, json, os, re, sys, urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

URL = "https://easycredit-bbl.de/statistiken/spieler"
KEYS = ["name", "team", "alter", "sp", "s", "n", "min", "pkt", "fgm", "fga", "fgp", "tpm", "tpa", "tpp", "ftm", "fta", "ftp",
        "oreb", "dreb", "reb", "ast", "tov", "stl", "blk", "pf", "dd2", "td3", "pm", "eff"]
# App-Spalte -> Feld der BBL-Daten; None = bei der BBL nicht vorhanden
QUELLE = {"alter": None, "sp": "gamesPlayed", "s": None, "n": None, "min": "secondsPerGame", "pkt": "pointsPerGame",
          "fgm": "fieldGoalsMadePerGame", "fga": "fieldGoalsAttemptedPerGame", "fgp": "fieldGoalsSuccessPercent",
          "tpm": "threePointShotsMadePerGame", "tpa": "threePointShotsAttemptedPerGame", "tpp": "threePointShotSuccessPercent",
          "ftm": "freeThrowsMadePerGame", "fta": "freeThrowsAttemptedPerGame", "ftp": "freeThrowsSuccessPercent",
          "oreb": "offensiveReboundsPerGame", "dreb": "defensiveReboundsPerGame", "reb": "totalReboundsPerGame",
          "ast": "assistsPerGame", "tov": "turnoversPerGame", "stl": "stealsPerGame", "blk": "blocksPerGame",
          "pf": "foulsCommittedPerGame", "dd2": "doubleDouble", "td3": "tripleDouble", "pm": "plusMinusPerGame",
          "eff": "efficiencyPerGame"}
GANZ = {"sp", "dd2", "td3"}
# BBL-Kürzel -> Team-Schlüssel der App (alle anderen sind gleich)
TEAM = {"BER": "ALBA", "FRS": "FRA", "HRO": "ROS"}
REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def seite(html_datei):
    if html_datei:
        return open(html_datei, encoding="utf-8").read()
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 (Korbjaeger-Update)", "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")


def zahl(v, ganz):
    if v is None:
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return int(round(v)) if ganz else round(v, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", default="")
    ap.add_argument("--ziel", default=os.path.join(REPO, "bbl-stats.json"))
    a = ap.parse_args()

    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', seite(a.html), re.S)
    if not m:
        sys.exit("Keine eingebetteten Daten (__NEXT_DATA__) gefunden - bbl-stats.json bleibt unverändert.")
    widgets = json.loads(m.group(1)).get("props", {}).get("pageProps", {}).get("preloadedWidgetData", {})
    w = next((v for k, v in widgets.items() if "season-players-statistics" in k), None)
    if not w or not isinstance(w.get("data"), list):
        sys.exit("Spielerstatistik nicht gefunden - bbl-stats.json bleibt unverändert.")

    jahr = int(w.get("activeSeason") or 0)
    saison = f"{jahr}-{(jahr + 1) % 100:02d}" if jahr else ""
    zeilen = []
    for e in w["data"]:
        p, t = e.get("seasonPlayer") or {}, e.get("seasonTeam") or {}
        name = f"{p.get('firstName', '').strip()} {p.get('lastName', '').strip()}".strip()
        team = TEAM.get(t.get("tlc", ""), t.get("tlc", ""))
        if not name or not team:
            continue
        z = [name, team]
        for key in KEYS[2:]:
            q = QUELLE.get(key)
            v = zahl(e.get(q), key in GANZ) if q else None
            if key == "min" and v is not None:
                v = round(v / 60, 1)  # Sekunden pro Spiel -> Minuten
            z.append(v)
        zeilen.append(z)

    # Lieber den alten Stand behalten als eine unvollständige Tabelle veröffentlichen (18 Teams, normal 200+ Spieler)
    if len(zeilen) < 150:
        sys.exit(f"Nur {len(zeilen)} Spieler gefunden - bbl-stats.json bleibt unverändert.")
    zeilen.sort(key=lambda z: -(z[KEYS.index("pkt")] or 0))

    try:
        bekannt = set(json.load(open(os.path.join(REPO, "data.json"), encoding="utf-8")).get("teams", {}))
        fehlt = sorted({z[1] for z in zeilen} - bekannt)
        if fehlt:
            print("Achtung, Team-Schlüssel fehlen in data.json/teams: " + ", ".join(fehlt))
    except Exception:
        pass

    kopf = {"quelle": "easycredit-bbl.de", "saison": saison, "art": "Hauptrunde, Durchschnitt pro Spiel",
            "stand": datetime.now(ZoneInfo("Europe/Berlin")).isoformat(timespec="seconds"), "spalten": KEYS}
    text = json.dumps(kopf, ensure_ascii=False)[:-1] + ',"spieler":[\n' + ",\n".join(json.dumps(z, ensure_ascii=False) for z in zeilen) + "\n]}"
    json.loads(text)
    with open(a.ziel, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"{os.path.basename(a.ziel)} geschrieben: {len(zeilen)} Spieler (Saison {saison})")


if __name__ == "__main__":
    main()
