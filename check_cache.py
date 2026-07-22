import requests
import re

r = requests.get('http://127.0.0.1:5000/', timeout=10)
# Find contest.js reference
match = re.search(r'contest\.js\?v=([^"&]+)', r.text)
if match:
    print('contest.js version:', match.group(1))
else:
    print('No version found')
    
# Check if compact layout is in the served content
if 'contest-compact' in r.text:
    print('OK: contest-compact found in HTML')
else:
    print('WARNING: contest-compact NOT in HTML')
