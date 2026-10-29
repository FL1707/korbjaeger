# Wandelt die im Browser von NBA.com ausgelesene Spielertabelle in nba-stats.json um.
# Eingabe: Datei mit dem Text "KJSTATS|<Kopfzeile>\n<Zeile>\n..." (auch als JSON-Hülle [{type,text}] eines gespeicherten Tool-Ergebnisses).
# Aufruf: powershell -NoProfile -ExecutionPolicy Bypass -File werkzeuge\nba-stats.ps1 -Quelle <Datei> [-Saison 2026-27]
param([Parameter(Mandatory = $true)][string]$Quelle, [string]$Saison = '2026-27', [string]$Ziel = '')
$ErrorActionPreference = 'Stop'
if (-not $Ziel) { $Ziel = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) '..\nba-stats.json' }
$KOPF = 'Player;Team;Age;GP;W;L;Min;PTS;FGM;FGA;FG%;3PM;3PA;3P%;FTM;FTA;FT%;OREB;DREB;REB;AST;TOV;STL;BLK;PF;DD2;TD3;+/-'
$KEYS = 'name','team','alter','sp','s','n','min','pkt','fgm','fga','fgp','tpm','tpa','tpp','ftm','fta','ftp','oreb','dreb','reb','ast','tov','stl','blk','pf','dd2','td3','pm'

$raw = [IO.File]::ReadAllText((Resolve-Path $Quelle), [Text.Encoding]::UTF8)
$txt = $null
try { $j = $raw | ConvertFrom-Json; foreach ($e in $j) { if ($e.text -like '*KJSTATS|*') { $txt = [string]$e.text; break } } } catch { }
if (-not $txt) { $txt = $raw }
$i = $txt.IndexOf('KJSTATS|'); if ($i -lt 0) { throw 'Kein "KJSTATS|" im Text gefunden.' }
$lines = @($txt.Substring($i + 8).Trim().Trim('"') -split '\\n|\r?\n' | Where-Object { $_ -match ';' })
if ($lines[0].Trim() -ne $KOPF) { throw "Unerwartete Kopfzeile: $($lines[0])" }

$inv = [Globalization.CultureInfo]::InvariantCulture
$rows = New-Object System.Collections.Generic.List[string]
foreach ($ln in $lines[1..($lines.Count - 1)]) {
  $c = $ln -split ';'
  if ($c.Count -ne 28 -or -not $c[0].Trim()) { continue }
  $vals = foreach ($x in $c[2..27]) { $v = 0.0; if ([double]::TryParse($x.Trim(), [Globalization.NumberStyles]::Float, $inv, [ref]$v)) { $v.ToString($inv) } else { 'null' } }
  $rows.Add('[' + (ConvertTo-Json -InputObject $c[0].Trim() -Compress) + ',' + (ConvertTo-Json -InputObject $c[1].Trim() -Compress) + ',' + ($vals -join ',') + ']')
}
# Lieber den alten Stand behalten als eine unvollständige Tabelle veröffentlichen
if ($rows.Count -lt 100) { throw "Nur $($rows.Count) Spieler gefunden - nba-stats.json bleibt unverändert." }

$kopf = [ordered]@{ quelle = 'NBA.com'; saison = $Saison; art = 'Regular Season, Durchschnitt pro Spiel'; stand = (Get-Date).ToString('yyyy-MM-ddTHH:mm:sszzz'); spalten = $KEYS } | ConvertTo-Json -Compress
$json = $kopf.TrimEnd('}') + ',"spieler":[' + "`n" + ($rows -join ",`n") + "`n]}"
$null = $json | ConvertFrom-Json
[IO.File]::WriteAllText([IO.Path]::GetFullPath($Ziel), $json, (New-Object Text.UTF8Encoding $false))
"nba-stats.json geschrieben: $($rows.Count) Spieler"
