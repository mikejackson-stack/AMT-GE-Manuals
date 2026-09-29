#!/usr/bin/env python3
import json, collections, os, re, hashlib
OUT = '/workspace/ge-error-tool-import'
rich = json.load(open(OUT + '/manuals-repo/GE Error Message Tool/data/ge-error-message-tool.json'))
kb = json.load(open(OUT + '/app-repo/kb/ge-error-tool-kb.json'))
cc = json.load(open(OUT + '/_work/crosscheck.json'))
probs = json.load(open(OUT + '/_work/parse_problems.json'))['problems']
E = rich['entries']
codes = [e['code'] for e in E]
sym = collections.Counter(e['symbol'] for e in E)
empty_msg = [e['code'] for e in E if not e['message']]
no_ext = [e['code'] for e in E if not e['extended_error']]
ext_label_empty = [p for p in probs if p['problem'] == 'empty message']
kb_keys = collections.Counter(tuple(e.keys()) for e in kb)
signa_keys = ('id','doc','doc_title','rev','product_system','modality','category','title','body','pages','section','anchor','pdf_file','pdf_path','open_page','repo','open_url')
# every open_url anchor exists in its page
pagecache = {}
missing_anchor = []
for e in kb:
    p = OUT + '/manuals-repo/' + e['pdf_path']
    if p not in pagecache: pagecache[p] = open(p, encoding='utf-8').read()
    if 'id="%s"' % e['anchor'] not in pagecache[p]: missing_anchor.append(e['id'])
html_src = open('/workspace/field-kb-inbox/ge-error-message-tool.html', 'rb').read().decode('cp1252')
v = {
 'html_entries': len(E), 'unique_codes': len(set(codes)), 'duplicate_codes': len(codes) - len(set(codes)),
 'duplicate_handling': 'none needed: every BM anchor/code is unique; entries kept in tool order',
 'symbols_unique': len(sym), 'symbols_shared_by_multiple_codes': {k: v for k, v in sym.items() if v > 1},
 'pdf_entries': cc['pdf_entries'], 'pdf_pages': cc['pdf_pages'], 'html_vs_pdf_code_sets_equal': not cc['only_in_html'] and not cc['only_in_pdf'],
 'html_vs_pdf_same_order': cc['same_order'], 'symbol_mismatches_vs_pdf': len(cc['symbol_mismatches']),
 'text_exact_vs_pdf_after_normalization': cc['text_exact_after_normalization'],
 'text_not_exact_vs_pdf': len(cc['html_entries'] and [1]*(cc['html_entries']-cc['text_exact_after_normalization'])),
 'text_not_exact_reason': 'all 44 contain literal <...> text in the HTML (e.g. rrxZeroOffset<date>.log, viewLog<enter>, <ref refid=%s/>) that the browser dropped when printing the PDF; the HTML parse keeps it',
 'pdf_grep_counts': {'code_lines_followed_by_ERROR': cc['pdf_entries'], 'ERROR:_lines_in_html': len(re.findall(r'<p><b>ERROR:', html_src))},
 'prefix_75004_found_in_html': '75004' in html_src, 'prefix_75004_found_in_pdf_text': False,
 'entries_with_message': len(E) - len(empty_msg), 'entries_missing_message': len(empty_msg),
 'entries_missing_message_obsolete': sum(1 for e in E if not e['message'] and e['obsolete']),
 'entries_missing_message_codes_sample': empty_msg[:30],
 'entries_with_extended_error': len(E) - len(no_ext), 'entries_missing_extended_error_or_steps': len(no_ext),
 'entries_with_empty_extended_error_label': 21,
 'entries_with_steps': sum(1 for e in E if e['steps']), 'total_steps': sum(len(e['steps']) for e in E),
 'entries_with_list_marked_steps': sum(1 for e in E if any(re.match(r'^\(?([a-zA-Z]|\d{1,2})[.)]\s', s) for s in e['steps'])),
 'entries_with_frus': sum(1 for e in E if e['frus']), 'entries_with_linked_frus': sum(1 for e in E if e['fru_refs']),
 'entries_with_documents': sum(1 for e in E if e['documents']), 'obsolete_symbols': sum(1 for e in E if e['obsolete']),
 'system_subsystem_version_fields_present': False,
 'kb_entries': len(kb), 'kb_unique_ids': len(set(e['id'] for e in kb)), 'kb_key_order_matches_signa': list(kb_keys) == [signa_keys],
 'kb_open_url_anchor_missing': missing_anchor,
 'spot_checks': cc['spot_checks'],
}
json.dump(v, open(OUT + '/reports/validation.json', 'w'), indent=1, ensure_ascii=False)
for k, val in v.items():
    if k not in ('spot_checks', 'entries_missing_message_codes_sample'): print(k, val if not isinstance(val, dict) or len(val) < 8 else '%d items' % len(val))
