#!/usr/bin/env python3
"""Adds the page-image reading results ('ground_truth') and fix-plan counts to each library/text_audit/<id>.json.
Inputs: .scratch/audit/reading/*.json (page-by-page readings) + MANUAL (pages read by the lead auditor)."""
import json, os, glob
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MANUAL = {  # lead auditor, read page image directly. word errors counted in body prose (>=150 words)
 'hodge_aid': [
  dict(page=268, body_words=~0 if False else 190, layer_word_errors=0, heading_lines_garbled=3, heading_lines_total=4, junk_lines=57, note='3 picture panels; 1 of 3 panel titles lost, footer garbled, whole picture OCR-ed to junk'),
  dict(page=100, body_words=330, layer_word_errors=0, fraction_errors=2, heading_lines_garbled=4, heading_lines_total=4, junk_lines=3, note='title, artist, date, footer all garbled; blurred credit block gives junk'),
  dict(page=244, body_words=330, layer_word_errors=1, heading_lines_garbled=4, heading_lines_total=4, junk_lines=2, note='PALETTE heading lost; Jateau for bateau'),
  dict(page=308, body_words=330, layer_word_errors=0, fraction_errors=2, heading_lines_garbled=3, heading_lines_total=3, junk_lines=2, note='date (910-11 missing digit; title block garbled'),
  dict(page=418, body_words=250, layer_word_errors=0, heading_lines_garbled=2, heading_lines_total=3, junk_lines=1, note='TREES heading garbled and in mid-body; Celan box heading missing')],
}
def load(n):
    p = f'{R}/.scratch/audit/reading/{n}.json'
    return json.load(open(p)) if os.path.exists(p) else []
READ = {'hodge_aid': load('hodge_rest'), 'hagen_wgps': load('hagen_set1') + load('hagen_set2'),
        'payne_gae': [x for x in load('digital_a') if x['book'] == 'payne_gae'],
        'grovier_nws': [x for x in load('digital_a') if x['book'] == 'grovier_nws'],
        'brookehitching_mad': [x for x in load('digital_b') if x['book'] == 'brookehitching_mad'],
        'dasal_artcurious': [x for x in load('digital_b') if x['book'] == 'dasal_artcurious']}
for b in READ:
    f = f'{R}/library/text_audit/{b}.json'
    d = json.load(open(f)); P = d['pages']
    pg = lambda c: [p['page'] for p in P if c(p)]
    d['ground_truth'] = {'readings_by_subagent_or_lead': READ[b], 'lead_manual_readings': MANUAL.get(b, []),
                         'note': 'counts from reading page images against text layer; see R4 report for totals and caveats'}
    d['fix_plan_counts'] = {
        'pages_no_text_layer': pg(lambda p: p['no_text_layer']),
        'pages_need_reader_garbled_heading_or_junk': pg(lambda p: p['garbled_headings'] > 0 or p['junk_lines'] >= 3),
        'pages_reading_order_flagged_by_geometry': pg(lambda p: p['reading_order_flag']),
        'pages_with_pullquote_dup': pg(lambda p: p['pullquote_dups'] > 0),
    }
    json.dump(d, open(f, 'w'), ensure_ascii=False, indent=0)
    print(b, {k: len(v) for k, v in d['fix_plan_counts'].items()})
