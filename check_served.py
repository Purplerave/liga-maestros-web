import requests
import re

r = requests.get('http://127.0.0.1:5000/', timeout=10)
# Find contest.js version
match = re.search(r'contest\.js\?v=([^"&]+)', r.text)
if match:
    print('contest.js version:', match.group(1))

# Check if new code is in the served JS
r2 = requests.get('http://127.0.0.1:5000/static/js/contest.js', timeout=10)
if 'contest-compact-general' in r2.text:
    print('OK: New layout code found in served JS')
else:
    print('ERROR: Old code still being served')
    
# Check line count
lines = r2.text.split('\n')
print('Total lines:', len(lines))
