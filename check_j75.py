import requests
urls = [
    'https://www.quiniela15.com/pronostico-quiniela/jornada-75',
    'https://www.quiniela15.com/quiniela/jornada-75',
]
for url in urls:
    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        print(f'{url}: {r.status_code}')
    except Exception as e:
        print(f'{url}: ERROR - {e}')
