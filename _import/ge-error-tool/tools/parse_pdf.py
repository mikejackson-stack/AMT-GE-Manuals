#!/usr/bin/env python3
"""Cross-check parser for the Chrome-printed PDF of the same tool (pdftotext, no -layout). Deterministic."""
import re, subprocess, sys
PDF_DEFAULT = '/workspace/field-kb-inbox/error-codes-2247373.pdf'

def pdf_text(pdf=PDF_DEFAULT):
    return subprocess.run(['pdftotext', '-enc', 'UTF-8', pdf, '-'], capture_output=True, check=True).stdout.decode('utf-8')

def parse(pdf=PDF_DEFAULT):
    t = pdf_text(pdf)
    pages = t.split('\f')
    lines = []  # (page, text)
    for pno, pg in enumerate(pages, 1):
        for ln in pg.split('\n'):
            lines.append((pno, ln.strip()))
    entries = []
    i = 0
    n = len(lines)
    while i < n:
        pno, ln = lines[i]
        if re.fullmatch(r'\d{4,9}', ln):
            j = i + 1
            while j < n and not lines[j][1]: j += 1
            if j < n and lines[j][1].startswith('ERROR:'):
                entries.append({'code': ln, 'page': pno, 'symbol': lines[j][1][6:].strip(), 'start': i, 'sym_line': j})
                i = j + 1; continue
        i += 1
    # entry text = lines between symbol line and 'Return To Top'
    for k, e in enumerate(entries):
        end = entries[k + 1]['start'] if k + 1 < len(entries) else n
        chunk = [l for _, l in lines[e['sym_line'] + 1:end]]
        txt = '\n'.join(chunk)
        txt = txt.split('Return To Top')[0]
        e['text'] = txt.strip()
        e['last_page'] = lines[end - 1][0] if end - 1 >= 0 else e['page']
    return entries, len(pages) - (1 if pages and not pages[-1].strip() else 0), t

if __name__ == '__main__':
    E, npages, t = parse(sys.argv[1] if len(sys.argv) > 1 else PDF_DEFAULT)
    print(len(E), 'entries over', npages, 'pages')
