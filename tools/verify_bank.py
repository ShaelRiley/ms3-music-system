#!/usr/bin/env python3
"""Verify every preserved source and every playable recording by SHA-256."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
receipt = json.loads((ROOT / 'preservation.json').read_text())
for row in receipt['files']:
    path = ROOT / row.get('relocatedTo', 'legacy/' + row['path'])
    data = path.read_bytes()
    assert len(data) == row['bytes'] and hashlib.sha256(data).hexdigest() == row['sha256'], str(path)
manifest = json.loads((ROOT / 'bank/manifest.json').read_text())
catalog = json.loads((ROOT / 'bank/catalog.json').read_text())
rows = {c['id']: c for c in manifest['clips']}
for row in manifest['clips'] + [manifest['bridge']]:
    data = (ROOT / 'bank' / row['path']).read_bytes()
    assert data[:4] == b'OggS' and len(data) == row['bytes']
    assert hashlib.sha256(data).hexdigest() == row['sha256']
for block in catalog['blocks'].values():
    for role in ('T0','T1','T2','T3','BOSS','VICTORY'):
        assert block['roles'][role] in catalog['assets']
for asset in catalog['assets'].values():
    assert 0 < asset['bound'] <= 2
    for index, clip in enumerate(asset['clips']):
        row = rows[clip['id']]
        assert clip['songIndex'] == index
        assert clip['path'] == row['path'] and clip['musicalFrames'] == row['musicalFrames']
        assert clip['duration'] == row['duration']
assert len(rows) == 224 and len(catalog['blocks']) == 8 and len(catalog['assets']) == 48
print(f"BANK_PASS: {len(receipt['files'])} preserved files; 224 clips + bridge; 8 blocks / 48 arrangements; exact original hashes")
