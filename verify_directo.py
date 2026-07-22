import requests
r = requests.get('http://127.0.0.1:5000/api/liga/data?j=74', timeout=10)
data = r.json()
all_matches = data.get('all_league_matches', [])
external = [m for m in all_matches if 'quiniela' not in str(m.get('id', ''))]
print('Total matches:', len(all_matches))
print('External matches:', len(external))
if external:
    for m in external[:3]:
        print(f'  {m.get("local")} vs {m.get("visitante")}')
else:
    print('  No external matches - Directo should be clean!')
