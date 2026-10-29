#!/usr/bin/env python3
# Holt die NBA-Spielerstatistik (Regular Season, Durchschnitt pro Spiel) von der öffentlichen ESPN-Schnittstelle
# und schreibt nba-stats.json im Format der App (gleiche Spalten wie die NBA.com-Variante werkzeuge/nba-stats.ps1).
# ESPN liefert keine Siege/Niederlagen je Spieler, keine Offensiv-/Defensiv-Rebounds und kein Plus-Minus: diese Spalten bleiben null.
# Namen werden, wo möglich, in der NBA.com-Schreibweise aus den vorhandenen nba-stats*.json übernommen (z. B. "Luka Dončić").
# Aufruf: python3 werkzeuge/nba-stats-espn.py --saison 2026-27     (schreibt nur, wenn ESPN genau diese Saison liefert)
#         python3 werkzeuge/nba-stats-espn.py --nur-saison         (gibt nur die laufende ESPN-Saison aus, z. B. 2026-27)
import argparse, glob, json, os, sys, unicodedata, urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

URL = ("https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/statistics/byathlete"
       "?region=us&lang=en&contentorigin=espn&isqualified=false&limit=200&sort=offensive.avgPoints:desc&seasontype=2&page={}")
KEYS = ["name", "team", "alter", "sp", "s", "n", "min", "pkt", "fgm", "fga", "fgp", "tpm", "tpa", "tpp", "ftm", "fta", "ftp",
        "oreb", "dreb", "reb", "ast", "tov", "stl", "blk", "pf", "dd2", "td3", "pm"]
# App-Spalte -> (ESPN-Kategorie, ESPN-Wert); None = bei ESPN nicht vorhanden
QUELLE = {"sp": ("general", "gamesPlayed"), "min": ("general", "avgMinutes"), "pkt": ("offensive", "avgPoints"),
          "fgm": ("offensive", "avgFieldGoalsMade"), "fga": ("offensive", "avgFieldGoalsAttempted"), "fgp": ("offensive", "fieldGoalPct"),
          "tpm": ("offensive", "avgThreePointFieldGoalsMade"), "tpa": ("offensive", "avgThreePointFieldGoalsAttempted"),
          "tpp": ("offensive", "threePointFieldGoalPct"), "ftm": ("offensive", "avgFreeThrowsMade"),
          "fta": ("offensive", "avgFreeThrowsAttempted"), "ftp": ("offensive", "freeThrowPct"), "reb": ("general", "avgRebounds"),
          "ast": ("offensive", "avgAssists"), "tov": ("offensive", "avgTurnovers"), "stl": ("defensive", "avgSteals"),
          "blk": ("defensive", "avgBlocks"), "pf": ("general", "avgFouls"), "dd2": ("general", "doubleDouble"),
          "td3": ("general", "tripleDouble")}
GANZ = {"alter", "sp", "dd2", "td3"}
# ESPN-Kürzel -> Team-Schlüssel der App (alle anderen sind gleich)
TEAM = {"GS": "GSW", "NY": "NYK", "SA": "SAS", "NO": "NOP", "UTAH": "UTA", "WSH": "WAS"}
REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def hole(seite):
    req = urllib.request.Request(URL.format(seite), headers={"User-Agent": "Mozilla/5.0 (Korbjaeger-Update)", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r)


def falten(s):
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower().replace(".", "").replace("'", "").strip()
    # Namenszusätze fehlen bei ESPN teilweise ("Bobby Portis" statt "Bobby Portis Jr.")
    for zusatz in (" jr", " sr", " ii", " iii", " iv"):
        if s.endswith(zusatz):
            s = s[: -len(zusatz)].strip()
    return s


def nba_namen():
    # Bekannte NBA.com-Schreibweisen aus allen vorhandenen Statistik-Dateien und den Star-Karten
    out = {}
    for f in sorted(glob.glob(os.path.join(REPO, "nba-stats*.json"))):
        try:
            d = json.load(open(f, encoding="utf-8"))
            for r in d.get("spieler", []):
                out.setdefault(falten(r[0]), r[0])
        except Exception:
            pass
    try:
        for p in json.load(open(os.path.join(REPO, "data.json"), encoding="utf-8")).get("stars", []):
            out[falten(p["name"])] = p["name"]
    except Exception:
        pass
    return out


def zahl(x, ganz):
    try:
        v = float(str(x).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return int(round(v)) if ganz else round(v, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--saison", default="")
    ap.add_argument("--ziel", default=os.path.join(REPO, "nba-stats.json"))
    ap.add_argument("--nur-saison", action="store_true")
    a = ap.parse_args()

    erste = hole(1)
    saison = erste.get("requestedSeason", {}).get("displayName", "")
    if a.nur_saison:
        print(saison)
        return
    if not a.saison or saison != a.saison:
        sys.exit(f"ESPN liefert Saison '{saison}', erwartet '{a.saison}' - nba-stats.json bleibt unverändert.")

    namen = {c["name"]: c["names"] for c in erste.get("categories", [])}
    athleten = list(erste.get("athletes", []))
    for s in range(2, int(erste.get("pagination", {}).get("pages", 1)) + 1):
        athleten += hole(s).get("athletes", [])

    bekannt, zeilen = nba_namen(), []
    for e in athleten:
        ath = e.get("athlete", {})
        werte = {}
        for k in e.get("categories", []):
            for n, v in zip(namen.get(k.get("name"), []), k.get("totals", [])):
                werte[(k.get("name"), n)] = v
        name = bekannt.get(falten(ath.get("displayName", "")), ath.get("displayName", "").strip())
        team = TEAM.get(ath.get("teamShortName", ""), ath.get("teamShortName", ""))
        if not name or not team:
            continue
        z = [name, team, zahl(ath.get("age"), True)]
        for key in KEYS[3:]:
            q = QUELLE.get(key)
            z.append(zahl(werte.get(q), key in GANZ) if q else None)
        zeilen.append(z)

    # Lieber den alten Stand behalten als eine unvollständige Tabelle veröffentlichen
    if len(zeilen) < 100:
        sys.exit(f"Nur {len(zeilen)} Spieler gefunden - nba-stats.json bleibt unverändert.")
    zeilen.sort(key=lambda z: -(z[KEYS.index("pkt")] or 0))

    kopf = {"quelle": "ESPN", "saison": saison, "art": "Regular Season, Durchschnitt pro Spiel",
            "stand": datetime.now(ZoneInfo("Europe/Berlin")).isoformat(timespec="seconds"), "spalten": KEYS}
    text = json.dumps(kopf, ensure_ascii=False)[:-1] + ',"spieler":[\n' + ",\n".join(json.dumps(z, ensure_ascii=False) for z in zeilen) + "\n]}"
    json.loads(text)
    with open(a.ziel, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"{os.path.basename(a.ziel)} geschrieben: {len(zeilen)} Spieler (Saison {saison})")


if __name__ == "__main__":
    main()
