import json

data = json.load(open('server/discogs_data_all.json', 'r', encoding='utf-8'))
items = data.get('data', [])

count = 0
for r in items:
    txt = json.dumps(r).lower()
    if 'bpm' in txt:
        title = r.get('title', '?')
        print(f'FOUND bpm in: {title}')
        for k, v in r.items():
            if 'bpm' in json.dumps(v).lower():
                print(f'  key={k}')
                if k == 'notes':
                    for line in str(v).split('\n'):
                        if 'bpm' in line.lower():
                            print(f'    {line.strip()}')
                elif k == 'tracklist':
                    for t in v:
                        if 'bpm' in json.dumps(t).lower():
                            print(f'    track: {t.get("title")}')
                            for tk, tv in t.items():
                                if 'bpm' in json.dumps(tv).lower():
                                    print(f'      {tk}: {tv}')
                elif k == 'ai':
                    ai = v
                    for ak, av in ai.items():
                        if 'bpm' in json.dumps(av).lower():
                            print(f'    ai.{ak}: {av}')
        count += 1
        if count >= 5:
            break

if count == 0:
    print('No bpm found in any release')
else:
    print(f'\nTotal releases with bpm: {count} (showing first 5)')
