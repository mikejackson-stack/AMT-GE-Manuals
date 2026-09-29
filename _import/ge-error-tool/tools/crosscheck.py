#!/usr/bin/env python3
import sys, re, json, random, difflib, collections
sys.path.insert(0, '/workspace/ge-error-tool-import/tools')
import parse_html, parse_pdf

def norm(s):
    s = s.replace('\u2019', "'").replace('\u201c', '"').replace('\u201d', '"').replace('\u00ae', '')
    return re.sub(r'[^a-z0-9%]+', '', s.lower())

def html_compare_text(e):
    t = e['message'] + ' ' + (('Extended Error: ' + e['extended_error']) if e['extended_error'] or 'x' else '')
    return t

def run(out_json=None, seed=20260929):
    meta, H, _ = parse_html.parse()
    P, npages, _ = parse_pdf.parse()
    hc = [e['code'] for e in H]; pc = [e['code'] for e in P]
    res = {'html_entries': len(H), 'pdf_entries': len(P), 'pdf_pages': npages,
           'html_unique': len(set(hc)), 'pdf_unique': len(set(pc)),
           'only_in_html': sorted(set(hc) - set(pc), key=int), 'only_in_pdf': sorted(set(pc) - set(hc), key=int),
           'same_order': hc == pc}
    pm = {e['code']: e for e in P}
    sym_mis, txt = [], []
    for e in H:
        p = pm.get(e['code'])
        if not p: continue
        if p['symbol'] != e['symbol']: sym_mis.append((e['code'], e['symbol'], p['symbol']))
        ptxt = p['text']
        # split PDF text into parts
        pparts = re.split(r'Extended Error:|Possible cause\(s\):|Documents', ptxt)
        h = norm(e['message'] + e['extended_error'] + ''.join(e['frus']) + ''.join(d['title'] for d in e['documents']))
        pp = norm(''.join(pparts))
        r = 1.0 if h == pp else difflib.SequenceMatcher(None, h, pp, autojunk=False).ratio()
        txt.append((r, e['code']))
    res['symbol_mismatches'] = sym_mis
    exact = sum(1 for r, _ in txt if r == 1.0)
    res['text_exact_after_normalization'] = exact
    res['text_ratio_ge_0_98'] = sum(1 for r, _ in txt if r >= 0.98)
    res['text_ratio_lt_0_98'] = sorted([(round(r, 4), c) for r, c in txt if r < 0.98])
    # spot checks
    rnd = random.Random(seed)
    sample = ['2247373'] + rnd.sample([c for c in hc if c != '2247373'], 10)
    hm = {e['code']: e for e in H}
    spots = []
    for c in sample:
        e, p = hm[c], pm[c]
        pparts = re.split(r'Extended Error:|Possible cause\(s\):|Documents', p['text'])
        h = norm(e['message'] + e['extended_error'] + ''.join(e['frus']) + ''.join(d['title'] for d in e['documents']))
        pp = norm(''.join(pparts))
        spots.append({'code': c, 'pdf_page': p['page'], 'symbol_html': e['symbol'], 'symbol_pdf': p['symbol'],
                      'symbol_match': e['symbol'] == p['symbol'], 'text_match_normalized': h == pp,
                      'ratio': round(difflib.SequenceMatcher(None, h, pp, autojunk=False).ratio(), 4),
                      'html_message': e['message'][:200], 'pdf_text_head': p['text'][:200]})
    res['spot_checks'] = spots
    res['pdf_page_of'] = {e['code']: e['page'] for e in P}
    if out_json:
        json.dump(res, open(out_json, 'w'), indent=1, ensure_ascii=False)
    return res

if __name__ == '__main__':
    r = run(sys.argv[1] if len(sys.argv) > 1 else None)
    for k in ('html_entries','pdf_entries','pdf_pages','html_unique','pdf_unique','same_order','text_exact_after_normalization','text_ratio_ge_0_98'):
        print(k, r[k])
    print('only_in_html', r['only_in_html'][:20], 'only_in_pdf', r['only_in_pdf'][:20])
    print('symbol_mismatches', len(r['symbol_mismatches']), r['symbol_mismatches'][:5])
    print('lt_0_98', len(r['text_ratio_lt_0_98']), r['text_ratio_lt_0_98'][:15])
    for s in r['spot_checks']: print(s['code'], s['pdf_page'], s['symbol_match'], s['text_match_normalized'], s['ratio'])
