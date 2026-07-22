import json
with open('C:/Users/Mortadelo/Desktop/QUINIELAs/LIGA_MAESTROS/data/LIVE_ALL_MATCHES_V3.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
if isinstance(data, list):
    live = [m for m in data if m.get('status') in ('LIVE', 'IN_PLAY', 'HT')]
    print('Live matches:', len(live))
    for m in live[:10]:
        print(f'  {m.get("local")} vs {m.get("visitante")} - Status: {m.get("status")}')
    if not live:
        print('  No live matches found')
        print('  Sample statuses:', set(m.get('status') for m in data[:20]))
else:
    print('Data type:', type(data))
