#!/usr/bin/env python3
"""Build the GE Error Message Tool import package (deterministic, stdlib only, no LLM)."""
import sys, os, json, html, hashlib, shutil, collections, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parse_html

OUT = '/workspace/ge-error-tool-import'
SRC = '/workspace/field-kb-inbox/ge-error-message-tool.html'
SET_DIR = 'GE Error Message Tool'
REPO = 'mikejackson-stack/AMT-GE-Manuals'
BASE = 'https://raw.githack.com/mikejackson-stack/AMT-GE-Manuals/main/GE%20Error%20Message%20Tool/'
DOC = 'Error Message Tool'
REV = 'Last Update 09/24/2011'
DOC_TITLE = 'GE MR Error Message Tool (GE System Log extended errors)'
PRODUCT = 'GE MR systems (Ermes error codes)'

def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()

def page_name(e):
    return 'ermes_%s.html' % e['code_block']

def kb_entry(e):
    msg = e['message'] if e['message'] else '(No message text in the Error Message Tool for this code.)'
    parts = ['ERROR: ' + e['symbol'], msg]
    if e['extended_error']:
        parts.append('Extended error: ' + e['extended_error'])
    if e['frus']:
        parts.append('Possible cause(s), most to least probable: ' + ', '.join(e['frus']))
    if e['documents']:
        parts.append('Documents (GE service desktop only): ' + ', '.join(d['title'] for d in e['documents']))
    pf = page_name(e)
    return {
        'id': 'ge_errtool_' + e['code'],
        'doc': DOC,
        'doc_title': DOC_TITLE,
        'rev': REV,
        'product_system': PRODUCT,
        'modality': 'MRI',
        'category': 'fault_code',
        'title': e['code'] + ' - ' + e['symbol'],
        'body': '\n'.join(parts),
        'pages': [1],
        'section': 'Error Message Tool > ' + (e['symbol_group'] or 'EM') + ' messages',
        'anchor': e['source_anchor'],
        'pdf_file': pf,
        'pdf_path': SET_DIR + '/root/' + pf,
        'open_page': 1,
        'repo': REPO,
        'open_url': BASE + 'root/' + pf + '#' + e['source_anchor'],
    }

CSS = ('body{font-family:Arial,Helvetica,sans-serif;max-width:900px;margin:0 auto;padding:12px;color:#111;line-height:1.4}'
       'header{border-bottom:2px solid #c00;margin-bottom:12px}.meta{font-size:.8rem;color:#555}'
       'section{border-bottom:1px solid #ccc;padding:10px 0}h2{margin:0;font-size:1.15rem;color:#b00}'
       '.sym{font-weight:bold;font-family:monospace}.txt{white-space:pre-wrap}.lbl{font-weight:bold;margin-top:6px}'
       'nav a{margin-right:12px}ol{margin:4px 0 0 20px;padding:0}')

def esc(s):
    return html.escape(s, quote=True)

def render_entry(e):
    h = ['<section id="%s"><a name="%s"></a>' % (e['source_anchor'], e['source_anchor']),
         '<h2>%s</h2>' % esc(e['code']),
         '<div class="sym">ERROR: %s</div>' % esc(e['symbol'])]
    h.append('<div class="txt">%s</div>' % (esc(e['message']) if e['message'] else '<i>(no message text in the tool)</i>'))
    if e['extended_error']:
        h.append('<div class="lbl">Extended Error:</div><div class="txt">%s</div>' % esc(e['extended_error']))
    if e['frus']:
        h.append('<div class="lbl">Possible cause(s) (most to least probable):</div><ol>%s</ol>'
                 % ''.join('<li>%s</li>' % esc(f) for f in e['frus']))
    if e['documents']:
        h.append('<div class="lbl">Documents (GE service desktop links, not available here):</div><ul>%s</ul>'
                 % ''.join('<li>%s</li>' % esc(d['title']) for d in e['documents']))
    h.append('</section>')
    return '\n'.join(h)

def page_html(title, nav, body, meta):
    return ('<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>%s</title><style>%s</style></head><body>\n<header><h1 style="font-size:1.3rem">%s</h1>'
            '<div class="meta">GE MR Error Message Tool &middot; Proprietary to General Electric &middot; %s &middot; '
            'converted for the AMT field KB from the original FrontPage HTML (text unchanged).</div>'
            '<nav>%s</nav></header>\n%s\n</body></html>\n') % (esc(title), CSS, esc(title), esc(meta['last_update_label']), nav, body)

def main():
    meta, E, problems = parse_html.parse(SRC)
    meta['last_update_label'] = 'Last Update 03:54:22 09/24/2011 UTC'
    crosscheck = json.load(open(os.path.join(OUT, '_work/crosscheck.json')))
    pdf_page = crosscheck['pdf_page_of']
    for e in E:
        e['pdf_cross_check_page'] = pdf_page.get(e['code'])
    man = os.path.join(OUT, 'manuals-repo'); app = os.path.join(OUT, 'app-repo')
    for d in (man, app):
        if os.path.exists(d): shutil.rmtree(d)
    setd = os.path.join(man, SET_DIR)
    os.makedirs(os.path.join(setd, 'root')); os.makedirs(os.path.join(setd, 'data')); os.makedirs(os.path.join(setd, 'source'))
    os.makedirs(os.path.join(app, 'kb'))

    # chunk pages, in numeric block order; entries inside a page keep the tool's order
    blocks = collections.OrderedDict()
    for e in sorted(E, key=lambda x: (int(x['code']) // 1000, x['source_order'])):
        blocks.setdefault(e['code_block'], []).append(e)
    names = list(blocks)
    for i, b in enumerate(names):
        prev = '<a href="ermes_%s.html">&larr; %s</a>' % (names[i-1], names[i-1]) if i else ''
        nxt = '<a href="ermes_%s.html">%s &rarr;</a>' % (names[i+1], names[i+1]) if i + 1 < len(names) else ''
        nav = '<a href="../index.html">All code blocks</a>' + prev + nxt
        body = '\n'.join(render_entry(e) for e in blocks[b])
        with open(os.path.join(setd, 'root', 'ermes_%s.html' % b), 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(page_html('Error codes %s (%d)' % (b, len(blocks[b])), nav, body, meta))
    rows = ''.join('<li><a href="root/ermes_%s.html">%s</a> &middot; %d codes</li>' % (b, b, len(blocks[b])) for b in names)
    intro = ('<p>%d error codes from the GE MR Error Message Tool (%s). Each code block page anchors every code as '
             '<code>#BM&lt;code&gt;</code>, as in the original tool. The original HTML is kept in '
             '<a href="source/Error%%20Message%%20Tool.html">source/</a>.</p>'
             '<p>Possible-cause (FRU) lists run from most to least probable. The tool says they are a suggestion only; do not order the complete list.</p>'
             '<ul>%s</ul>') % (len(E), meta['last_update_label'], rows)
    with open(os.path.join(setd, 'index.html'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(page_html('GE MR Error Message Tool', '', intro, meta))
    shutil.copyfile(SRC, os.path.join(setd, 'source', 'Error Message Tool.html'))

    # rich normalized data
    for e in E:
        e.pop('message_raw_lines', None)
    rich = {'source': {k: meta[k] for k in ('title', 'last_update', 'proprietary_notice', 'source_bytes', 'source_sha256')},
            'source_file_in_repo': SET_DIR + '/source/Error Message Tool.html',
            'cross_check_pdf': {'file': 'error-codes-2247373.pdf', 'pages': 3136, 'bytes': os.path.getsize('/workspace/field-kb-inbox/error-codes-2247373.pdf'),
                                'sha256': sha('/workspace/field-kb-inbox/error-codes-2247373.pdf')},
            'field_notes': {
                'code': 'Ermes error number exactly as listed in the tool (anchor BM<code>).',
                'full_code/prefix': 'The tool lists bare Ermes numbers only; no "<prefix>:" form (e.g. 75004:) exists in the HTML or the PDF, so full_code == code and prefix is null. The app matches "<prefix>:<code>" queries by searching the part after the colon.',
                'code_block': 'Thousand-block used to split the HTML pages (not a GE category).',
                'symbol_group': 'Second token of the EM_ symbol (e.g. DIAG, RF, GP); derived, not a GE field.',
                'message': 'Error message text; hard line wraps joined, breaks kept before list items, "Label: %s" fields and after a trailing colon.',
                'extended_error': 'Extended Error text, unwrapped the same way. Verbatim wording.',
                'steps': 'extended_error split in order: list items (a), 1.) whole, other lines by sentence. Derived for display; extended_error is authoritative.',
                'frus': 'Possible cause(s), in tool order (most to least probable).',
                'fru_refs': 'Original GE service-desktop hrefs for linked FRUs (dead outside the scanner).',
                'documents': 'Document links in 2 entries (GE eServDocs, dead outside the scanner).',
                'system/subsystem/software_version': 'Not present in the tool; always null.',
                'pdf_cross_check_page': 'Page in error-codes-2247373.pdf where the code starts.'},
            'count': len(E), 'entries': E}
    rich_path = os.path.join(setd, 'data', 'ge-error-message-tool.json')
    head = {k: v for k, v in rich.items() if k != 'entries'}
    with open(rich_path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(json.dumps(head, ensure_ascii=False, indent=1)[:-2] + ',\n "entries": [\n')
        fh.write(',\n'.join(json.dumps(e, ensure_ascii=False, separators=(',', ':')) for e in E))
        fh.write('\n ]\n}\n')

    # KB (app schema) - compact like ge-signa-kb.json
    kb = [kb_entry(e) for e in E]
    signa = open('/workspace/sprint/kb/ge-signa-kb.json', 'rb').read()
    sep = (', ', ': ') if signa[:40].find(b'", "') != -1 else (',', ':')
    kb_bytes = json.dumps(kb, ensure_ascii=False, separators=sep).encode('utf-8')
    for p in (os.path.join(app, 'kb', 'ge-error-tool-kb.json'), os.path.join(man, 'ge-error-tool-kb.json')):
        open(p, 'wb').write(kb_bytes)
    json.dump({'problems': problems}, open(os.path.join(OUT, '_work', 'parse_problems.json'), 'w'), indent=1)
    print('entries', len(E), 'pages', len(names), 'kb bytes', len(kb_bytes), 'sha', hashlib.sha256(kb_bytes).hexdigest())

if __name__ == '__main__':
    main()
