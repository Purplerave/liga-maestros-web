import requests
r = requests.get('http://127.0.0.1:5000/api/liga/data?j=74', timeout=10)
data = r.json()
print('Partidos J74:', len(data.get('partidos', [])))
print('All league matches:', len(data.get('all_league_matches', [])))
if data.get('all_league_matches'):
    for m in data['all_league_matches'][:5]:
        print(f'  {m.get("local")} vs {m.get("visitante")} - {m.get("status")}')
else:
    print('  No league matches found')
