import requests
r = requests.get('http://127.0.0.1:5000/api/liga/data?j=74', timeout=10)
data = r.json()

print('=== J74 PARTIDOS ===')
partidos = data.get('partidos', [])
print(f'Total: {len(partidos)}')
for p in partidos[:3]:
    print(f'  #{p.get("num")}: {p.get("local")} vs {p.get("visitante")} - {p.get("status")} ({p.get("fecha")} {p.get("hora")})')

print('\n=== ALL LEAGUE MATCHES ===')
all_matches = data.get('all_league_matches', [])
print(f'Total: {len(all_matches)}')
for m in all_matches[:5]:
    print(f'  {m.get("local")} vs {m.get("visitante")} - {m.get("status")} - League: {m.get("league", m.get("competition", "unknown"))}')
