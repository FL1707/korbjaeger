#!/usr/bin/env python3
# Schreibt spielplan-lang.json: alle kommenden Spiele der nächsten 3 Monate für den Tab „Upcoming“.
# NBA und Euroleague holt das Skript selbst aus öffentlichen Schnittstellen (ESPN-Scoreboard, api-live.euroleague.net).
# Alle anderen Ligen (BBL, BCL, DBB) trägt die Update-Routine von Hand in spielplan-lang.json ein; das Skript lässt
# diese Einträge stehen und entfernt nur vergangene Spiele. Die nahen Spiele mit TV- und Info-Angaben stehen weiter in
# data.json → spielplan; die App führt beide Listen zusammen (data.json hat Vorrang).
# Aufruf: python3 werkzeuge/spielplan.py
import json, os, sys, urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

TAGE = 92
BERLIN = ZoneInfo("Europe/Berlin")
REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
ZIEL = os.path.join(REPO, "spielplan-lang.json")
AUTO = {"NBA", "EL"}  # diese Ligen schreibt das Skript selbst
# ESPN-Kürzel -> Team-Schlüssel der App (alle anderen sind gleich)
NBA_TEAM = {"GS": "GSW", "NY": "NYK", "SA": "SAS", "NO": "NOP", "UTAH": "UTA", "WSH": "WAS"}
# Euroleague-Klubcode -> Team-Schlüssel der App
EL_TEAM = {"BAR": "BAR", "PAR": "PAR", "OLY": "OLY", "PAM": "VAL", "BES": "BES", "VIR": "VIR", "DUB": "DUB", "ASV": "ASV",
           "PRS": "PBB", "MUN": "FCB", "PAN": "PAO", "MAD": "RMA", "TEL": "MTA", "BAS": "BAS", "RED": "CZV", "MIL": "EA7",
           "IST": "EFS", "HTA": "HTA", "ZAL": "ZAL", "ULK": "FEN"}


def hole(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Korbjaeger-Update)", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def berlin(utc):
    # "2026-11-01T20:30Z" oder "2026-11-01T20:30:00Z" -> ISO mit deutschem Offset
    t = datetime.fromisoformat(utc.replace("Z", "+00:00"))
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t.astimezone(BERLIN).isoformat(timespec="seconds")


def nba(von, bis, teams, fehlt):
    spiele, monat = [], datetime(von.year, von.month, 1, tzinfo=BERLIN)
    while monat <= bis:
        for e in hole(f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={monat:%Y%m}&limit=1000").get("events", []):
            if e.get("status", {}).get("type", {}).get("state") != "pre":
                continue
            c = e["competitions"][0]["competitors"]
            heim = next((x for x in c if x.get("homeAway") == "home"), None)
            gast = next((x for x in c if x.get("homeAway") == "away"), None)
            if not heim or not gast:
                continue
            h = NBA_TEAM.get(heim["team"].get("abbreviation", ""), heim["team"].get("abbreviation", ""))
            g = NBA_TEAM.get(gast["team"].get("abbreviation", ""), gast["team"].get("abbreviation", ""))
            if h not in teams or g not in teams:
                fehlt.add(f"NBA {heim['team'].get('abbreviation')}/{gast['team'].get('abbreviation')}")
                continue
            spiele.append({"liga": "NBA", "zeit": berlin(e["date"]), "heim": h, "gast": g})
        monat = (monat + timedelta(days=32)).replace(day=1)
    return spiele


def euroleague(teams, fehlt):
    jetzt = datetime.now(BERLIN)
    jahr = jetzt.year if jetzt.month >= 7 else jetzt.year - 1  # Saison E2026 läuft von Herbst 2026 bis Frühjahr 2027
    spiele = []
    for e in hole(f"https://api-live.euroleague.net/v2/competitions/E/seasons/E{jahr}/games").get("data", []):
        if e.get("played"):
            continue
        h, g = EL_TEAM.get(e["local"]["club"]["code"]), EL_TEAM.get(e["road"]["club"]["code"])
        if not h or not g or h not in teams or g not in teams:
            fehlt.add(f"EL {e['local']['club']['code']}/{e['road']['club']['code']}")
            continue
        s = {"liga": "EL", "zeit": berlin(e["utcDate"]), "heim": h, "gast": g}
        if not e.get("confirmedHour", True):
            s["ohneZeit"] = True
        spiele.append(s)
    return spiele


def main():
    sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")
    teams = set(json.load(open(os.path.join(REPO, "data.json"), encoding="utf-8")).get("teams", {}))
    try:
        alt = json.load(open(ZIEL, encoding="utf-8"))
    except Exception:
        alt = {}
    jetzt = datetime.now(BERLIN)
    bis = jetzt + timedelta(days=TAGE)
    im_fenster = lambda s: jetzt - timedelta(hours=3) < datetime.fromisoformat(s["zeit"]) <= bis

    fehlt, neu, fehler = set(), [], []
    for liga, holen in (("NBA", lambda: nba(jetzt, bis, teams, fehlt)), ("EL", lambda: euroleague(teams, fehlt))):
        try:
            neu += holen()
        except Exception as e:
            # Quelle nicht erreichbar: die bisherigen Spiele dieser Liga behalten
            fehler.append(liga)
            neu += [s for s in alt.get("spiele", []) if s.get("liga") == liga]
            print(f"{liga}: Abruf fehlgeschlagen ({e}) – alte Einträge bleiben", file=sys.stderr)
    # Von Hand gepflegte Ligen (BBL, BCL, DBB) bleiben unverändert
    neu += [s for s in alt.get("spiele", []) if s.get("liga") not in AUTO]
    spiele = sorted((s for s in neu if im_fenster(s)), key=lambda s: (s["zeit"], s["liga"], s["heim"]))

    kopf = {"hinweis": "Kommende Spiele der nächsten 3 Monate für den Tab Upcoming. NBA und EL schreibt werkzeuge/spielplan.py, "
                       "BBL, BCL und DBB die Update-Routine. Die nahen Spiele mit TV/Info stehen in data.json → spielplan.",
            "stand": jetzt.isoformat(timespec="seconds"), "bis": bis.date().isoformat()}
    text = json.dumps(kopf, ensure_ascii=False)[:-1] + ',"spiele":[\n' + ",\n".join(json.dumps(s, ensure_ascii=False) for s in spiele) + "\n]}"
    json.loads(text)
    with open(ZIEL, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    zahl = {}
    for s in spiele:
        zahl[s["liga"]] = zahl.get(s["liga"], 0) + 1
    print(f"spielplan-lang.json geschrieben: {len(spiele)} Spiele bis {bis.date()} {zahl}")
    if fehlt:
        print("Ohne Team-Schlüssel übersprungen (in data.json → teams ergänzen):", ", ".join(sorted(fehlt)))


if __name__ == "__main__":
    main()
