import requests, json

data = json.load(open('server/discogs_data_all.json', 'r', encoding='utf-8'))
items = data.get('data', [])

# Find a release we know has BPM in notes
target = next((r for r in items if 'Everybody, Everywhere' in r.get('title', '')), None)
if not target:
    print('Target release not found')
    exit(1)

rid = target.get('release_id') or target.get('id')
print(f'Release: {target["title"]}, ID: {rid}')

resp = requests.get(f'https://api.discogs.com/releases/{rid}', headers={'User-Agent': 'TestApp/1.0'}, timeout=15)
print(f'Status: {resp.status_code}')

if resp.status_code == 200:
    d = resp.json()
    print('Top-level keys:', sorted(d.keys()))
    print()
    # Check tracklist structure
    for i, t in enumerate(d.get('tracklist', [])[:3]):
        print(f'Track {i}: keys={sorted(t.keys())}')
        if 'extraartists' in t:
            for ea in t['extraartists'][:2]:
                print(f'  extraartist: {ea}')
    print()
    # Check notes for BPM
    notes = d.get('notes', '')
    for line in notes.split('\n'):
        if 'bpm' in line.lower() or 'tempo' in line.lower():
            print(f'notes line: {line.strip()}')
    print()
    # Check if there's any 'bpm' or 'tempo' key anywhere
    txt = json.dumps(d)
    for key in ['bpm', 'tempo', 'BPM']:
        if key in txt:
            print(f'Found "{key}" in response JSON')
else:
    print(f'Error: {resp.text[:200]}')
