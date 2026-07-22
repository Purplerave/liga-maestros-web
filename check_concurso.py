with open('C:/Users/Mortadelo/Desktop/QUINIELAs/LIGA_MAESTROS/static/js/contest.js', 'r', encoding='utf-8') as f:
    content = f.read()
idx = content.find('if (view === "CONTEST_GENERAL")')
if idx >= 0:
    snippet = content[idx:idx+2000]
    print('CONTEST_GENERAL section:')
    print(snippet[:1500])
