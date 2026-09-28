#!/usr/bin/env python3
"""Verify an AMT-GE-Manuals working tree against file-manifest.json.

Usage (run from the repo root, or pass --root):
  python3 verify_manifest.py                      # check every manifest path
  python3 verify_manifest.py --batch 12           # only files completed by push batch 12
  python3 verify_manifest.py --batch 1-12         # a range of batches (cumulative check)
  python3 verify_manifest.py --git-sha1           # also check git blob sha1
Options: --manifest PATH (default: ./file-manifest.json, else next to this script), --root DIR (default: .)
Exit code 0 = all good, 1 = missing/mismatched files, 2 = usage/manifest error.
Also reports leftover transport chunks (*.xfer-NN) which must never be committed.
"""
import argparse, hashlib, json, os, sys

def sums(path, want_git):
    h = hashlib.sha256(); size = os.path.getsize(path)
    g = hashlib.sha1(b'blob %d\0' % size) if want_git else None
    with open(path, 'rb') as f:
        for blk in iter(lambda: f.read(1 << 20), b''):
            h.update(blk)
            if g: g.update(blk)
    return size, h.hexdigest(), (g.hexdigest() if g else None)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--manifest'); ap.add_argument('--root', default='.')
    ap.add_argument('--batch', help='N or A-B'); ap.add_argument('--git-sha1', action='store_true')
    a = ap.parse_args()
    mpath = a.manifest or next((p for p in ('file-manifest.json', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'file-manifest.json')) if os.path.exists(p)), None)
    if not mpath or not os.path.exists(mpath): print('manifest not found'); return 2
    M = json.load(open(mpath)); files = M['files']
    if a.batch:
        lo, _, hi = a.batch.partition('-'); lo = int(lo); hi = int(hi or lo)
        files = [f for f in files if lo <= f.get('batch', -1) <= hi]
    missing, bad = [], []
    for i, f in enumerate(files, 1):
        p = os.path.join(a.root, f['path'])
        if not os.path.isfile(p): missing.append(f['path']); continue
        size, sh, gs = sums(p, a.git_sha1)
        if size != f['bytes'] or sh != f['sha256'] or (a.git_sha1 and gs != f['git_sha1']):
            bad.append((f['path'], size, f['bytes']))
        if i % 5000 == 0: print(f'  ...{i}/{len(files)}', file=sys.stderr)
    leftovers = []
    for sd in {f['path'].split('/', 1)[0] for f in files}:
        for r, _, fs in os.walk(os.path.join(a.root, sd)):
            leftovers += [os.path.join(r, x) for x in fs if '.xfer-' in x]
    print(f'checked {len(files)} files: ok {len(files)-len(missing)-len(bad)}, missing {len(missing)}, mismatched {len(bad)}, leftover .xfer chunks {len(leftovers)}')
    for m in missing[:50]: print('MISSING', m)
    for b in bad[:50]: print('MISMATCH', *b)
    for l in leftovers[:20]: print('LEFTOVER', l)
    return 0 if not (missing or bad or leftovers) else 1

if __name__ == '__main__':
    sys.exit(main())
