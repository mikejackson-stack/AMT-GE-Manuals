#!/usr/bin/env python3
"""Verify the GE Error Message Tool import in an AMT-GE-Manuals checkout (run from the repo root).
  python3 _import/ge-error-tool/verify.py [--strict]
Checks sha256+bytes of every manifest file, the KB JSON (count, unique ids, key order),
and that every KB open_url anchor exists in its page. --strict also fails on extra files
under 'GE Error Message Tool/' and on leftover *.tar.gz archives in the repo root."""
import hashlib, json, os, sys, glob, urllib.parse
HERE = os.path.dirname(os.path.abspath(__file__))
man = json.load(open(os.path.join(HERE, 'manifest.json')))
strict = '--strict' in sys.argv
bad = []
for f in man['files']:
    p = f['path']
    if not os.path.isfile(p): bad.append(('missing', p)); continue
    b = open(p, 'rb').read()
    if len(b) != f['bytes'] or hashlib.sha256(b).hexdigest() != f['sha256']: bad.append(('mismatch', p))
kb = json.load(open('ge-error-tool-kb.json', encoding='utf-8'))
keys = ['id','doc','doc_title','rev','product_system','modality','category','title','body','pages','section','anchor','pdf_file','pdf_path','open_page','repo','open_url']
if len(kb) != man['kb_entries']: bad.append(('kb count', len(kb)))
if len({e['id'] for e in kb}) != len(kb): bad.append(('kb duplicate ids', ''))
pages = {}
for e in kb:
    if list(e.keys()) != keys: bad.append(('kb keys', e['id'])); break
    if e['pdf_path'] not in pages:
        pages[e['pdf_path']] = open(e['pdf_path'], encoding='utf-8').read() if os.path.isfile(e['pdf_path']) else ''
    if 'id="%s"' % e['anchor'] not in pages[e['pdf_path']]: bad.append(('anchor missing', e['id']))
    exp = man['open_url_base'] + urllib.parse.quote(e['pdf_path'][len('GE Error Message Tool/'):]) + '#' + e['anchor']
    if e['open_url'] != exp: bad.append(('open_url', e['id']))
if strict:
    listed = {f['path'] for f in man['files']}
    for p in glob.glob('GE Error Message Tool/**/*', recursive=True):
        if os.path.isfile(p) and p not in listed: bad.append(('extra', p))
    for p in glob.glob('*.tar.gz'): bad.append(('leftover archive', p))
for b in bad[:50]: print('BAD', *b)
print('files', len(man['files']), 'kb', len(kb), 'problems', len(bad))
print('RESULT', 'OK' if not bad else 'FAIL')
sys.exit(0 if not bad else 1)
