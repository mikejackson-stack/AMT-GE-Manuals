#!/usr/bin/env python3
"""Verify the "Signa Sprint/" set in an AMT-GE-Manuals checkout against manifest.json.

Local mode (default, run inside the checkout):
  python3 _import/signa-sprint/verify.py [--repo-dir .] [--batch N] [--git-sha1] [--strict] [--json out.json]
    - hashes every manifest file on disk (sha256 + byte size; --git-sha1 also checks the git blob id)
    - --batch N limits the "missing" check to files of batch N (and earlier batches with --upto)
    - reports extra files under "Signa Sprint/" not in the manifest, and leftover
      transport files anywhere in the set (*.tar.gz, *.part-NN, *.xfer-NN, *.dlpart, *.REASSEMBLE.txt)
Remote mode (read-only, needs `gh`):
  python3 verify.py --branch <branch> [--gh-repo owner/name] [--git-sha1]
    - compares blob sizes (and SHA-1 with --git-sha1) in the branch tree to the manifest.
Exit code 0 = nothing missing (in scope), no mismatches, no leftover chunks (and no extras with --strict).
"""
import argparse, hashlib, json, os, re, subprocess, sys, urllib.parse

CHUNK_RE = re.compile(r'(\.(part|xfer)-\d+$)|(\.dlpart$)|(\.tar\.gz$)|(\.tgz$)|(\.REASSEMBLE\.txt$)', re.I)

def gh(path):
    p = subprocess.run(['gh', 'api', '-H', 'Accept: application/vnd.github+json', path], capture_output=True, text=True)
    if p.returncode != 0:
        raise SystemExit(f'gh api {path} failed: {p.stderr.strip()}')
    return json.loads(p.stdout)

def list_tree(repo, sha, prefix=''):
    t = gh(f'repos/{repo}/git/trees/{sha}?recursive=1')
    out = {}
    if not t.get('truncated'):
        for e in t['tree']:
            if e['type'] == 'blob': out[prefix + e['path']] = (e.get('size'), e['sha'])
        return out
    t = gh(f'repos/{repo}/git/trees/{sha}')
    for e in t['tree']:
        if e['type'] == 'blob': out[prefix + e['path']] = (e.get('size'), e['sha'])
        elif e['type'] == 'tree': out.update(list_tree(repo, e['sha'], prefix + e['path'] + '/'))
    return out

def hash_file(p):
    h = hashlib.sha256(); n = os.path.getsize(p)
    g = hashlib.sha1(b'blob %d\0' % n)
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b); g.update(b)
    return n, h.hexdigest(), g.hexdigest()

def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument('--manifest', default=os.path.join(here, 'manifest.json'))
    ap.add_argument('--repo-dir', default='.', help='AMT-GE-Manuals checkout root (default: cwd)')
    ap.add_argument('--batch', type=int, default=None, help='only require files of this batch')
    ap.add_argument('--upto', action='store_true', help='with --batch N: require batches 1..N')
    ap.add_argument('--git-sha1', action='store_true', help='also check git blob SHA-1')
    ap.add_argument('--strict', action='store_true', help='fail on extra files under the set folder')
    ap.add_argument('--branch', default=None, help='remote mode: check this branch via gh api instead of disk')
    ap.add_argument('--gh-repo', default=None)
    ap.add_argument('--json', default=None)
    a = ap.parse_args()
    man = json.load(open(a.manifest, encoding='utf-8'))
    root = man.get('destination_root', 'Signa Sprint/').strip('/')
    files = man['files']
    def in_scope(f):
        if a.batch is None: return True
        return f.get('batch') == a.batch or (a.upto and (f.get('batch') or 0) <= a.batch)
    want = {f['path']: f for f in files}
    rep = {'root': root, 'manifest_files': len(files), 'checked': 0, 'ok': 0, 'missing': [], 'size_mismatch': [],
           'sha256_mismatch': [], 'git_sha1_mismatch': [], 'extra': [], 'leftover_chunks': []}
    if a.branch:
        repo = a.gh_repo or man.get('target_repo', 'mikejackson-stack/AMT-GE-Manuals')
        br = gh(f'repos/{repo}/branches/{urllib.parse.quote(a.branch, safe="")}')
        cur = br['commit']['commit']['tree']['sha']
        for part in root.split('/'):
            t = gh(f'repos/{repo}/git/trees/{cur}')
            hit = [e for e in t['tree'] if e['path'] == part and e['type'] == 'tree']
            cur = hit[0]['sha'] if hit else None
            if not cur: break
        have = {root + '/' + k: v for k, v in (list_tree(repo, cur) if cur else {}).items()}
        rep.update({'mode': 'branch', 'repo': repo, 'branch': a.branch, 'commit': br['commit']['sha']})
        for p, f in want.items():
            if not in_scope(f): continue
            rep['checked'] += 1
            if p not in have: rep['missing'].append(p); continue
            size, sha = have[p]; bad = False
            if size != f['bytes']: rep['size_mismatch'].append({'path': p, 'expected': f['bytes'], 'actual': size}); bad = True
            if a.git_sha1 and sha != f['git_sha1']: rep['git_sha1_mismatch'].append(p); bad = True
            if not bad: rep['ok'] += 1
        disk = set(have)
    else:
        base = os.path.abspath(a.repo_dir)
        rep.update({'mode': 'local', 'repo_dir': base})
        for p, f in want.items():
            fp = os.path.join(base, *p.split('/'))
            if not os.path.isfile(fp):
                if in_scope(f): rep['checked'] += 1; rep['missing'].append(p)
                continue
            rep['checked'] += 1
            n, s256, s1 = hash_file(fp); bad = False
            if n != f['bytes']: rep['size_mismatch'].append({'path': p, 'expected': f['bytes'], 'actual': n}); bad = True
            if s256 != f['sha256']: rep['sha256_mismatch'].append(p); bad = True
            if a.git_sha1 and s1 != f['git_sha1']: rep['git_sha1_mismatch'].append(p); bad = True
            if not bad: rep['ok'] += 1
        disk = set()
        rd = os.path.join(base, root)
        for dp, ds, fs in os.walk(rd):
            ds[:] = [d for d in ds if d != '.git']
            for fn in fs: disk.add(os.path.relpath(os.path.join(dp, fn), base).replace(os.sep, '/'))
    for p in sorted(disk - set(want)):
        (rep['leftover_chunks'] if CHUNK_RE.search(p) else rep['extra']).append(p)
    fail = bool(rep['missing'] or rep['size_mismatch'] or rep['sha256_mismatch'] or rep['git_sha1_mismatch']
                or rep['leftover_chunks'] or (a.strict and rep['extra']))
    rep['result'] = 'FAIL' if fail else 'OK'
    scope = f"batch {a.batch}{' (and earlier)' if a.upto else ''}" if a.batch else 'all batches'
    print(f"[{rep['mode']}] {root}/ vs manifest ({len(files)} files, scope: {scope})")
    print(f"  checked {rep['checked']}  ok {rep['ok']}  missing {len(rep['missing'])}  size_mm {len(rep['size_mismatch'])}  "
          f"sha256_mm {len(rep['sha256_mismatch'])}  git_sha1_mm {len(rep['git_sha1_mismatch'])}  "
          f"extra {len(rep['extra'])}  leftover_chunks {len(rep['leftover_chunks'])}")
    for k in ('missing', 'size_mismatch', 'sha256_mismatch', 'git_sha1_mismatch', 'leftover_chunks', 'extra'):
        for x in rep[k][:20]: print(f'  {k}: {x}')
        if len(rep[k]) > 20: print(f'  {k}: ... {len(rep[k]) - 20} more')
    print('RESULT:', rep['result'])
    if a.json: json.dump(rep, open(a.json, 'w'), indent=1)
    sys.exit(1 if fail else 0)

if __name__ == '__main__':
    main()
