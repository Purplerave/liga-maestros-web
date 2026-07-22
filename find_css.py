import requests
import re

r = requests.get('http://127.0.0.1:5000/', timeout=10)
# Find all CSS references
css_refs = re.findall(r'href="([^"]*contest[^"]*\.css[^"]*)"', r.text)
for ref in css_refs:
    print(ref)
