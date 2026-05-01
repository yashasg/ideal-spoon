#!/usr/bin/env python3
"""Frank one-off raw pull: Wehewehe public-domain dictionaries.

Downloads PD (pre-1925) full PDFs from puke.ulukau.org for the 6 PD-cleared
dictionaries hosted under wehewehe.org's `hdict` collection. Also captures
ToS/about pages, dictionary landing pages, sample entry surfaces, and emits
a JSONL manifest per dictionary.
"""
import urllib.request, json, hashlib, time, datetime as dt, sys, re
from pathlib import Path

ROOT=Path('/Users/yashasgujjar/dev/ideal-spoon')
RAW=ROOT/'data/raw/wehewehe-stage2/20260501'
UA={'User-Agent':'ideal-spoon/0.1 (Frank stage2 raw acquisition; github.com/yashasg/ideal-spoon)'}
RATE=1.2

# (ebook_oid, wehewehe_tag, label, pub_year)
PD_DICTS = [
    ('EBOOK-VOCABULARY','textvocabulary','Andrews 1836 — A vocabulary of words in the Hawaiian language',1836),
    ('EBOOK-emd',       'textemd',       'Emerson 1845 — He hoakakaolelo no na huaolelo Beritania',1845),
    ('EBOOK-ANDREW',    'textandrew',    'Andrews 1865 — A dictionary of the Hawaiian language',1865),
    ('EBOOK-CDD',       'textcdd',       'Dictionary of Biblical Words 1872 — He buke wehiwehi huaolelo Baibala',1872),
    ('EBOOK-ehd',       'textehd',       'Hitchcock 1887 — An English-Hawaiian dictionary',1887),
    ('EBOOK-PARKER',    'textparker',    'Parker 1922 — A dictionary of the Hawaiian language (revised)',1922),
]

# Inventory-only (rights TBD or modern copyright)
INVENTORY = [
    ('EBOOK-PED',       'textpukuielbert','Pukui-Elbert Hawaiian Dictionary (1986) — copyrighted, INVENTORY ONLY','1986'),
    ('EBOOK-MKD',       'textmamaka',    'Māmaka Kaiao (2003) — copyrighted, INVENTORY ONLY','2003'),
    ('EBOOK-IHL',       'textihl',       'Judd/Pukui/Stokes 1943 — pre-1978; rights review pending','1943'),
    ('EBOOK-THW01',     'textthw',       'Kent 1986 — copyrighted, INVENTORY ONLY','1986'),
    ('EBOOK-PEPN',      'textpeplace',   'Place Names of Hawaiʻi (1974) — copyrighted, INVENTORY ONLY','1974'),
    ('EBOOK-CPN',       'textclark',     'Hawaiʻi Place Names (2002) — copyrighted, INVENTORY ONLY','2002'),
    ('EBOOK-DHLLT',     'texthllt',      'Hawaiian Legal Land-Terms (1995) — copyrighted, INVENTORY ONLY','1995'),
    (None,              'textchd',       'Combined Hawaiian Dictionary (2020) — aggregator, INVENTORY ONLY','2020'),
]

def fetch(url, attempts=3):
    last=None
    for i in range(attempts):
        try:
            r=urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=120)
            return r.status, r.headers.get('Content-Type',''), r.read()
        except Exception as e:
            last=e; time.sleep(2**i)
    raise last

def stream(url, dest:Path, chunk=1<<20):
    dest.parent.mkdir(parents=True,exist_ok=True)
    h=hashlib.sha256(); n=0
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=600) as r, dest.open('wb') as f:
        ct=r.headers.get('Content-Type','')
        cl=r.headers.get('Content-Length')
        while True:
            buf=r.read(chunk)
            if not buf: break
            f.write(buf); h.update(buf); n+=len(buf)
    return ct,cl,n,h.hexdigest()

def sha(b): return hashlib.sha256(b).hexdigest()
def now(): return dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

def main():
    manifest=[]

    # ToS / about pages
    print('[1/4] ToS pages')
    tos=[
        ('wehewehe_root','https://wehewehe.org/','wehewehe_root.html'),
        ('hdict_about','https://wehewehe.org/gsdl2.85/cgi-bin/hdict?a=p&p=about','hdict_about.html'),
        ('hdict_help_en','https://wehewehe.org/gsdl2.85/cgi-bin/hdict?a=p&p=help&l=en','hdict_help_en.html'),
        ('hdict_home','https://wehewehe.org/gsdl2.85/cgi-bin/hdict?a=p&p=home&l=haw','hdict_home_haw.html'),
        ('puke_root','https://puke.ulukau.org/?l=haw','puke_root_haw.html'),
        ('ulukau_copyright','https://ulukau.org/php-include/disclaimer.php?subpage=copyright&l=en&subpage_heading=Terms+of+use','ulukau_copyright.html'),
        ('ulukau_about','https://ulukau.org/php-include/disclaimer.php?subpage=about&l=en','ulukau_about.html'),
        ('ulukau_privacy','https://ulukau.org/php-include/disclaimer.php?subpage=privacy&l=en','ulukau_privacy.html'),
        ('robots','https://wehewehe.org/robots.txt','robots.txt'),
    ]
    for tag,url,fn in tos:
        try:
            st,ct,b=fetch(url)
            p=RAW/'tos'/fn; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(b)
            manifest.append({'kind':'tos','tag':tag,'source_url':url,'local_path':str(p.relative_to(ROOT)),'fetched_at':now(),'http_status':st,'content_type':ct,'bytes':len(b),'sha256':sha(b),'mode':'tos'})
            print(' ',tag,st,len(b))
        except Exception as e:
            print(' ',tag,'ERR',e)
        time.sleep(RATE)

    # Sample entry probes (haw + en sides) — 3 PD-meaningful headwords
    print('[2/4] sample entry probes')
    PROBES=['aloha','wai','akua','iho','mauna','keiki']
    for q in PROBES:
        for l in ['haw','en']:
            url=f'https://wehewehe.org/gsdl2.85/cgi-bin/hdict?a=q&q={q}&l={l}'
            try:
                st,ct,b=fetch(url)
                p=RAW/'sample_entries'/f'{q}__l-{l}.html'
                p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(b)
                manifest.append({'kind':'sample_query','query':q,'lang':l,'source_url':url,'local_path':str(p.relative_to(ROOT)),'fetched_at':now(),'http_status':st,'content_type':ct,'bytes':len(b),'sha256':sha(b),'mode':'smoke'})
            except Exception as e:
                print(' ',q,l,'ERR',e)
            time.sleep(RATE)

    # PD dictionary landings + PDFs
    print('[3/4] PD dictionary landings + PDFs')
    for oid,tag,label,year in PD_DICTS:
        # landing
        landing_url=f'https://puke.ulukau.org/?a=d&d={oid}&l=haw'
        try:
            st,ct,b=fetch(landing_url)
            p=RAW/'toc'/f'{oid}__landing.html'; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(b)
            manifest.append({'kind':'landing','dict_id':oid,'wehewehe_tag':tag,'label':label,'pub_year':year,'source_url':landing_url,'local_path':str(p.relative_to(ROOT)),'fetched_at':now(),'http_status':st,'content_type':ct,'bytes':len(b),'sha256':sha(b),'mode':'full'})
            print(' ',oid,'landing',st,len(b))
        except Exception as e:
            print(' ',oid,'landing ERR',e)
        time.sleep(RATE)
        # pdf
        pdf_url=f'https://ulukau.org/ulukau-books/cgi-bin/imageserver.pl?oid={oid}&getpdf=true'
        dest=RAW/'pdfs'/f'{oid}.pdf'
        try:
            ct,cl,n,h=stream(pdf_url,dest)
            manifest.append({'kind':'pdf','dict_id':oid,'wehewehe_tag':tag,'label':label,'pub_year':year,'source_url':pdf_url,'local_path':str(dest.relative_to(ROOT)),'fetched_at':now(),'content_type':ct,'content_length_header':cl,'bytes':n,'sha256':h,'rights_note':'PD by US copyright term (pre-1929)','mode':'full'})
            print(' ',oid,'pdf',n)
        except Exception as e:
            print(' ',oid,'pdf ERR',e)
            manifest.append({'kind':'pdf','dict_id':oid,'error':str(e),'source_url':pdf_url,'fetched_at':now(),'mode':'failed'})
        time.sleep(RATE)

    # Inventory only (no PDF pull, just landing)
    print('[4/4] inventory landings (no PDF pull, copyrighted/TBD)')
    for oid,tag,label,year in INVENTORY:
        if oid is None:
            manifest.append({'kind':'inventory','dict_id':None,'wehewehe_tag':tag,'label':label,'pub_year':year,'mode':'inventory_only','rights_note':'aggregator; per-component rights apply','fetched_at':now()})
            continue
        landing_url=f'https://puke.ulukau.org/?a=d&d={oid}&l=haw'
        try:
            st,ct,b=fetch(landing_url)
            p=RAW/'toc'/f'{oid}__landing.html'; p.write_bytes(b)
            manifest.append({'kind':'inventory_landing','dict_id':oid,'wehewehe_tag':tag,'label':label,'pub_year':year,'source_url':landing_url,'local_path':str(p.relative_to(ROOT)),'fetched_at':now(),'http_status':st,'content_type':ct,'bytes':len(b),'sha256':sha(b),'mode':'inventory_only','rights_note':'modern copyright or pending review; PDF NOT downloaded'})
            print(' ',oid,'inv',st,len(b))
        except Exception as e:
            print(' ',oid,'inv ERR',e)
        time.sleep(RATE)

    mfpath=RAW/'manifest.jsonl'
    with mfpath.open('w') as f:
        for r in manifest: f.write(json.dumps(r,ensure_ascii=False)+'\n')

    summary={
        'source_id':'wehewehe-stage2',
        'source_name':'Wehewehe (wehewehe.org) — PD subset via puke.ulukau.org',
        'fetch_date_utc':now(),
        'rate_limit_seconds':RATE,
        'fetcher':'scripts/_frank_pull_wehewehe.py',
        'tos_url':'https://ulukau.org/php-include/disclaimer.php?subpage=copyright',
        'rights_summary':('PD-cleared subset (6 dictionaries pre-1925) downloaded as full PDF; '
            'modern dictionaries (Pukui-Elbert 1986, Māmaka Kaiao 2003, Kent 1986, Place Names 1974/2002, '
            'Hawaiian Legal Land-Terms 1995, Combined 2020) inventory-only — landing page captured, no PDF pull. '
            'Judd/Pukui/Stokes 1943 inventory-only pending US renewal-status check by Linus.'),
        'rights_status':'mixed; PD-pre-1925 cleared; modern inventory-only',
        'release_eligible':False,'prototype_only':True,
        'pd_dicts':[{'oid':o,'tag':t,'label':l,'year':y} for o,t,l,y in PD_DICTS],
        'inventory_only':[{'oid':o,'tag':t,'label':l,'year':y} for o,t,l,y in INVENTORY],
        'counts':{
            'tos_pages':sum(1 for r in manifest if r.get('kind')=='tos'),
            'sample_queries':sum(1 for r in manifest if r.get('kind')=='sample_query'),
            'pd_pdfs':sum(1 for r in manifest if r.get('kind')=='pdf' and r.get('mode')=='full'),
            'pd_pdf_failures':sum(1 for r in manifest if r.get('kind')=='pdf' and r.get('mode')=='failed'),
            'pd_landings':sum(1 for r in manifest if r.get('kind')=='landing'),
            'inventory_landings':sum(1 for r in manifest if r.get('kind')=='inventory_landing'),
        },
    }
    (RAW/'manifest_summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False))
    print(json.dumps(summary['counts'],indent=2))

if __name__=='__main__':
    main()
