#!/usr/bin/env python3
"""Frank one-off raw pull: Ka Hoʻoilina trilingual sections.

Saves raw HTML responses for ~331 leaf section OIDs (orig HAW + modernized HAW + English),
plus ToS / editorial-intro pages and a JSONL manifest. Local-only; gitignored under data/.
"""
import urllib.request, urllib.error, json, hashlib, time, os, datetime as dt, sys, re
from pathlib import Path

ROOT = Path('/Users/yashasgujjar/dev/ideal-spoon')
RAW = ROOT/'data/raw/hooilina-stage2/20260501'
UA = {'User-Agent':'ideal-spoon/0.1 (Frank stage2 raw acquisition; github.com/yashasg/ideal-spoon)'}
RATE = 1.2  # seconds between requests; site says crawl-delay 1
E_DOC = 'd-0journal--00-0-0-004-Document---0-1--1haw-50---20-frameset---ka--001-0110escapewin'
E_PAGE = 'p-0journal--00-0-0-004-Document---0-1--1haw-50---20-welcome-----001-0110escapewin'

LAYER_BY_SUFFIX = {3:'haw_orig', 5:'haw_modern', 7:'en'}

def fetch(url, attempts=3):
    last=None
    for i in range(attempts):
        try:
            r=urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=45)
            return r.status, r.headers.get('Content-Type',''), r.read()
        except Exception as e:
            last=e; time.sleep(2**i)
    raise last

def save(path: Path, body: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)

def sha(b): return hashlib.sha256(b).hexdigest()
def now(): return dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

def main():
    nodes = json.load(open(RAW/'classifier/all_classifier_nodes.json'))
    docs = nodes['docs']

    manifest = []

    # 1. ToS / about / edintro / home
    print('[1/4] ToS + editorial pages')
    tos_targets = [
        ('home_root', 'https://hooilina.org/', 'home_root.html'),
        ('home_cgi', f'https://hooilina.org/cgi-bin/journal?e={E_PAGE}&l=en', 'home_cgi_en.html'),
        ('edintro_haw', f'https://hooilina.org/cgi-bin/journal?a=p&p=edintro&gg=text', 'edintro.html'),
        ('about', f'https://hooilina.org/cgi-bin/journal?a=p&p=about', 'about.html'),
        ('subinfo', f'https://hooilina.org/cgi-bin/journal?a=p&p=subinfo', 'subinfo.html'),
        ('contact', f'https://hooilina.org/cgi-bin/journal?a=p&p=contact', 'contact.html'),
        ('disclaimer', 'https://ulukau.org/disclaimer.php', 'ulukau_disclaimer.html'),
        ('robots', 'https://hooilina.org/robots.txt', 'robots.txt'),
    ]
    for tag, url, fn in tos_targets:
        try:
            st, ct, body = fetch(url)
            p = RAW/'tos'/fn
            save(p, body)
            manifest.append({
                'kind':'tos','tag':tag,'source_url':url,'local_path':str(p.relative_to(ROOT)),
                'fetched_at':now(),'http_status':st,'content_type':ct,'bytes':len(body),'sha256':sha(body),
                'rights_note':'editorial-layer (c) 2002-2004 Kamehameha Schools; underlying 19c sources PD by age',
                'mode':'tos',
            })
            print(' ',tag,st,len(body))
        except Exception as e:
            print(' ',tag,'ERR',e)
        time.sleep(RATE)

    # 2. Parent doc metadata (the 4 root HASHes)
    print('[2/4] parent doc landing pages')
    roots = sorted({d.split('.')[0] for d in docs})
    for r in roots:
        for variant, e_state in [('p_frame',E_PAGE),('d_state',E_DOC)]:
            url=f'https://hooilina.org/cgi-bin/journal?e={e_state}&a=d&d={r}&gg=text'
            try:
                st,ct,body=fetch(url)
                p=RAW/'parent_docs'/f'{r}__{variant}.html'
                save(p,body)
                manifest.append({
                    'kind':'parent_doc','doc_id':r,'variant':variant,'source_url':url,
                    'local_path':str(p.relative_to(ROOT)),'fetched_at':now(),
                    'http_status':st,'content_type':ct,'bytes':len(body),'sha256':sha(body),
                    'mode':'parent_doc',
                })
                print(' ',r[:25],variant,st,len(body))
            except Exception as e:
                print(' ',r,variant,'ERR',e)
            time.sleep(RATE)

    # 3. All section bodies (3-layer: orig/modern/english)
    print(f'[3/4] section bodies (n={len(docs)})')
    for i,d in enumerate(docs):
        suffix=int(d.split('.')[-1])
        layer=LAYER_BY_SUFFIX.get(suffix,f'unknown_{suffix}')
        url=f'https://hooilina.org/cgi-bin/journal?e={E_DOC}&cl=search&d={d}&d2=1&gg=text'
        out_path=RAW/'sections'/layer/f'{d}.html'
        try:
            st,ct,body=fetch(url)
            save(out_path,body)
            manifest.append({
                'kind':'section','doc_id':d,'layer':layer,'oid_root':d.split('.')[0],
                'oid_path':'.'.join(d.split('.')[1:]),'language':('haw' if layer.startswith('haw') else 'en'),
                'spelling_layer':layer,'source_url':url,'local_path':str(out_path.relative_to(ROOT)),
                'fetched_at':now(),'http_status':st,'content_type':ct,'bytes':len(body),'sha256':sha(body),
                'rights_note':'editorial-layer (c) Kamehameha Schools 2002-2004; original-HAW source PD by age; reuse requires citing source HAW',
                'mode':'full',
            })
            if (i+1)%25==0: print(f'  {i+1}/{len(docs)}')
        except Exception as e:
            print('  ERR',d,e)
            manifest.append({'kind':'section','doc_id':d,'error':str(e),'source_url':url,'fetched_at':now(),'mode':'failed'})
        time.sleep(RATE)

    # 4. Manifest
    print('[4/4] writing manifest')
    mfpath=RAW/'manifest.jsonl'
    with mfpath.open('w') as f:
        for row in manifest:
            f.write(json.dumps(row,ensure_ascii=False)+'\n')
    summary={
        'source_id':'hooilina-stage2',
        'source_name':'Ka Hoʻoilina (hooilina.org)',
        'fetch_date_utc':now(),
        'rate_limit_seconds':RATE,
        'fetcher':'scripts/_frank_pull_hooilina.py',
        'tos_url':'https://hooilina.org/cgi-bin/journal?a=p&p=edintro&gg=text',
        'rights_summary':('Editorial layers (modernized HAW + English) (c) 2002-2004 Kamehameha Schools; '
            'underlying 19c source documents PD by age. Per editor intro: "Ua noa i ka lehulehu akea ... '
            'me ke koina nae" — reuse free with the requirement that original source HAW be cited alongside '
            'any reuse of the modernized HAW or English layer.'),
        'rights_status':'permission_with_attribution_required',
        'release_eligible':False,'prototype_only':True,
        'counts':{
            'tos_pages':sum(1 for r in manifest if r.get('kind')=='tos'),
            'parent_docs':sum(1 for r in manifest if r.get('kind')=='parent_doc'),
            'sections_total':sum(1 for r in manifest if r.get('kind')=='section'),
            'sections_failed':sum(1 for r in manifest if r.get('mode')=='failed'),
            'sections_haw_orig':sum(1 for r in manifest if r.get('layer')=='haw_orig'),
            'sections_haw_modern':sum(1 for r in manifest if r.get('layer')=='haw_modern'),
            'sections_en':sum(1 for r in manifest if r.get('layer')=='en'),
        },
        'parent_doc_ids':sorted({r['doc_id'] for r in manifest if r.get('kind')=='parent_doc'}),
    }
    (RAW/'manifest_summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False))
    print(json.dumps(summary['counts'],indent=2))

if __name__=='__main__':
    main()
