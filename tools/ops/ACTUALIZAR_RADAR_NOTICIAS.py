import json
import urllib.request


URL = "http://127.0.0.1:5000/api/noticias/radar?force=1"


if __name__ == "__main__":
    with urllib.request.urlopen(URL, timeout=40) as response:
        payload = json.loads(response.read().decode("utf-8"))
    print(f"Radar actualizado: {payload.get('fetched_at', '-')}")
    print(f"Noticias: {len(payload.get('items', []))}")
    for item in payload.get("items", [])[:5]:
        print(f"- [{item.get('source')}] {item.get('title')}")
    if payload.get("errors"):
        print("\nFuentes con incidencias:")
        for err in payload["errors"]:
            print(f"  * {err}")
