import requests

r = requests.get("https://ligademaestros.alwaysdata.net/api/liga/data?j=1", timeout=10)
d = r.json()
print("La Liga top 5:")
for t in d["standings"]["primera"][:5]:
    print(f"  {t['pos']}. {t['n']} - {t['pts']}pts pj:{t['pj']}")
print()
print("Segunda top 5:")
for t in d["standings"]["segunda"][:5]:
    print(f"  {t['pos']}. {t['n']} - {t['pts']}pts pj:{t['pj']}")
