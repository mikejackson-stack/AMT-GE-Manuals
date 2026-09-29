#!/usr/bin/env python3
"""Deterministic parser for the GE MR "Error Message Tool" HTML (Last Update 03:54:22 09/24/2011 UTC).
No LLM. stdlib only.  Output: normalized rich entries (list of dicts) in tool order.
"""
import re, html, json, sys, hashlib

SRC_DEFAULT = '/workspace/field-kb-inbox/ge-error-message-tool.html'
# Real HTML tags used by the FrontPage page. Anything else between < > (e.g. <date>, <enter>,
# <ref refid=%s/>, <1st process ID>) is literal message text and is kept.
HTML_TAGS = {'p','br','b','font','a','blockquote','u','i','em','strong','span','li','ul','ol',
             'td','tr','table','hr','div','center','small','big','sup','sub','pre','tt','code'}
TAG_RE = re.compile(r'<\s*(/?)\s*([A-Za-z][A-Za-z0-9]*)\b([^<>]*)>')

def strip_html(frag):
    """HTML fragment -> text with '\n' for <br>/<p> breaks; non-HTML <...> kept literally."""
    def rep(m):
        name = m.group(2).lower()
        if name not in HTML_TAGS:
            return m.group(0)
        if name == 'br':
            return '\n'
        if name == 'p' or name == 'li' or name == 'tr':
            return '\n\n' if not m.group(1) else '\n\n'
        return ''
    frag = re.sub(r'\s+', ' ', frag)          # source newlines are just whitespace in HTML
    t = TAG_RE.sub(rep, frag)
    t = html.unescape(t).replace('\xa0', ' ')
    lines = [re.sub(r'[ \t\r\f\v]+', ' ', ln).strip() for ln in t.split('\n')]
    out, blank = [], False
    for ln in lines:
        if not ln:
            blank = True; continue
        if blank and out: out.append('')
        out.append(ln); blank = False
    return '\n'.join(out).strip()

LIST_RE = re.compile(r'^(\(?([a-zA-Z]|\d{1,2}|[ivx]{1,4})[.)]|[-*\u2022\u00b7]|Step\s*\d+[:.)]?)\s+')
FIELD_RE = re.compile(r'^[A-Za-z][\w /().#\[\]-]{0,40}\s*[:=]\s*%')

def unwrap(text):
    """Join hard-wrapped lines. Keep a break before list items / 'Label: %s' fields and after ':'"""
    out = []
    for para in text.split('\n\n'):
        cur = []
        for ln in para.split('\n'):
            ln = ln.strip()
            if not ln: continue
            if cur and not (LIST_RE.match(ln) or FIELD_RE.match(ln) or cur[-1].endswith(':')):
                cur[-1] = cur[-1] + ' ' + ln
            else:
                cur.append(ln)
        if cur: out.append('\n'.join(cur))
    return '\n'.join(out).strip()

ABBR = re.compile(r'(\b(e\.g|i\.e|etc|approx|Rev|No|vs|Fig|Ref|Sect|Ver|min|max|esp|incl|Dr|St)\.|\b[A-Z]\.)$')
def sentences(line):
    parts = re.split(r'(?<=[.!?])\s+(?=[A-Z(\'"])', line)
    out = []
    for p in parts:
        if out and ABBR.search(out[-1]):
            out[-1] += ' ' + p
        else:
            out.append(p)
    return [p.strip() for p in out if p.strip()]

def steps_from(ext_unwrapped):
    """Ordered troubleshooting steps: list items stay whole; other lines split into sentences."""
    steps = []
    for ln in ext_unwrapped.split('\n'):
        ln = ln.strip()
        if not ln: continue
        if LIST_RE.match(ln):
            steps.append(ln)
        else:
            steps.extend(sentences(ln))
    return steps

def flat(t):
    return re.sub(r'\s+', ' ', t).strip()

def parse(path=SRC_DEFAULT):
    raw = open(path, 'rb').read()
    d = raw.decode('cp1252')   # page declares ISO-8859-1; cp1252 maps the 0x92-0x94 smart quotes correctly
    m = re.search(r'Last Update ([0-9:]+) ([0-9/]+) UTC', d)
    last_update = f'{m.group(2)} {m.group(1)} UTC' if m else ''
    parts = re.split(r'<a name="BM(\d+)">', d)
    entries, problems = [], []
    for idx in range(1, len(parts), 2):
        anchor_code = parts[idx]
        blk = parts[idx + 1]
        vis = re.match(r'\s*([^<]*)</a>', blk)
        vis_code = vis.group(1).strip() if vis else ''
        bq = re.search(r'<blockquote>(.*?)</blockquote>', blk, re.S)
        body = bq.group(1) if bq else ''
        if not bq: problems.append({'code': anchor_code, 'problem': 'no blockquote'})
        body = re.split(r'<a href="#1__Introduction">', body)[0]   # drop "Return To Top"
        sm = re.search(r'<p><b>ERROR:\s*([^<]*?)\s*</p>', body)
        symbol = sm.group(1).strip() if sm else ''
        rest = body[sm.end():] if sm else body
        # documents block (<b><u>Documents</u></b> + links)
        documents = []
        dm = re.search(r'<b><u>Documents</u></b>(.*)$', rest, re.S)
        if dm:
            for a in re.finditer(r'<a\s+href="([^"]*)"[^>]*>(.*?)</a>', dm.group(1), re.S):
                documents.append({'title': flat(strip_html(a.group(2))), 'href': html.unescape(a.group(1))})
            rest = rest[:dm.start()]
        pc_frag = ''
        pcm = re.search(r'<b>Possible cause\(s\):\s*</b>(.*)$', rest, re.S)
        if pcm:
            pc_frag = pcm.group(1); rest = rest[:pcm.start()]
        ext_frag = ''
        em = re.search(r'<b>Extended Error:\s*</b>(.*)$', rest, re.S)
        if em:
            ext_frag = em.group(1); rest = rest[:em.start()]
        msg_raw = strip_html(rest)
        ext_raw = strip_html(ext_frag)
        # FRUs: anchors (with internal service-desktop href) or plain comma list
        frus, fru_refs = [], []
        if pc_frag:
            pc_text = flat(strip_html(pc_frag))
            refs = []
            def _tok(a):
                refs.append((flat(strip_html(a.group(2))), html.unescape(a.group(1)).split('"+TARGET')[0]))
                return '\x00%d\x00' % (len(refs) - 1)
            tok = re.sub(r'<a\s+href="([^"]*)"[^>]*>(.*?)</a>', _tok, pc_frag, flags=re.S)
            tok_text = flat(strip_html(tok))
            empty_slots = 0
            for item in re.split(r'\s*,\s*', tok_text):
                item = item.strip()
                if not item:
                    empty_slots += 1; continue
                mm = re.fullmatch(r'\x00(\d+)\x00', item)
                if mm:
                    name, href = refs[int(mm.group(1))]
                    frus.append(name); fru_refs.append({'fru': name, 'href': href})
                else:
                    item = re.sub(r'\x00(\d+)\x00', lambda k: refs[int(k.group(1))][0], item)
                    frus.append(item)
            if empty_slots and len(frus):
                problems.append({'code': anchor_code, 'problem': 'empty FRU slot(s) in source list', 'count': empty_slots})
        msg_u = unwrap(msg_raw)
        ext_u = unwrap(ext_raw)
        e = {
            'code': anchor_code,
            'full_code': anchor_code,
            'prefix': None,
            'code_block': f'{int(anchor_code)//1000*1000}-{int(anchor_code)//1000*1000+999}',
            'symbol': symbol,
            'symbol_group': (symbol.split('_')[1] if symbol.startswith('EM_') and '_' in symbol[3:] or symbol.startswith('EM_') else ''),
            'obsolete': symbol.startswith('EM_OBSOLETE'),
            'message': msg_u,
            'message_raw_lines': msg_raw,
            'extended_error': ext_u,
            'steps': steps_from(ext_u) if ext_u else [],
            'frus': frus,
            'fru_refs': fru_refs,
            'documents': documents,
            'system': None, 'subsystem': None, 'software_version': None,
            'source_anchor': 'BM' + anchor_code,
            'source_order': len(entries) + 1,
        }
        if vis_code != anchor_code:
            problems.append({'code': anchor_code, 'problem': 'visible code differs from anchor', 'visible': vis_code})
        if not symbol: problems.append({'code': anchor_code, 'problem': 'no ERROR: symbol'})
        if not msg_u: problems.append({'code': anchor_code, 'problem': 'empty message'})
        entries.append(e)
    meta = {'source_file': path, 'source_bytes': len(raw), 'source_sha256': hashlib.sha256(raw).hexdigest(),
            'title': 'Error Message Tool', 'last_update': last_update, 'proprietary_notice': 'Proprietary to General Electric'}
    return meta, entries, problems

if __name__ == '__main__':
    meta, entries, problems = parse(sys.argv[1] if len(sys.argv) > 1 else SRC_DEFAULT)
    print(json.dumps(meta, indent=1)); print(len(entries), 'entries;', len(problems), 'problems')
