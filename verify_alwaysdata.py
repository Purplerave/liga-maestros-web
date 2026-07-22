import requests
r = requests.get('https://ligademaestros.alwaysdata.net/api/concurso?j=74', timeout=15)
data = r.json()
print('Concurso jornada:', data.get('jornada', {}).get('jornada'))
print('General rows:', len(data.get('general', [])))
if data.get('jornada', {}).get('rows'):
    print('J74 predictions:', len(data['jornada']['rows']))
    for row in data['jornada']['rows'][:5]:
        name = row.get('name', 'Unknown')
        points = row.get('points', 0)
        print(f'  {name}: {points} pts')
