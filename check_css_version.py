import requests
import re

r = requests.get('http://127.0.0.1:5000/', timeout=10)
# Find contest.css reference
match = re.search(r'contest\.css\?v=([^"&]+)', r.text)
if match:
    print('contest.css version:', match.group(1))
else:
    print('No contest.css version found')
