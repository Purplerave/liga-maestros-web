import requests
r = requests.get('https://ligademaestros.alwaysdata.net/api/liga/data?j=74', timeout=15)
data = r.json()
preds = data.get('predicciones_actuales', {})
penya = ['baidu', 'geli', 'kimi', 'pepe', 'profe', 'chipi', 'fortu', 'gema', 'jimmy', 'sesudo', 'fistro']
print('La Peña predictions on alwaysdata:')
for user in penya:
    user_data = preds.get(user, {})
    signos = user_data.get('signos', [])
    if signos:
        joined = " ".join(signos[:15])
        print(f'  {user:12s}: {joined}')
    else:
        print(f'  {user:12s}: NO DATA')
