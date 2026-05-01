#!/usr/bin/env python3
"""Frank one-off raw pull: HK statutes — complete raw bytes pass.

Augments existing `data/raw/hawaiian-kingdom-statutes-paired-imprints/20260501/`
(8 djvu.txt OCR files already on disk) with source PDFs, DjVu page XML,
hOCR searchtext, IA item metadata (XML + MARC), and a full per-item manifest.
"""
import urllib.request, json, hashlib, time, datetime as dt
from pathlib import Path

ROOT=Path('/Users/yashasgujjar/dev/ideal-spoon')
RAW=ROOT/'data/raw/hawaiian-kingdom-statutes-paired-imprints/20260501'
RAW.mkdir(parents=True,exist_ok=True)
UA={'User-Agent':'ideal-spoon/0.1 (Frank stage2 raw acquisition; github.com/yashasg/ideal-spoon)'}
RATE=1.5

ITEMS=[
    ('esrp641724381','en','1897-penal-laws'),
    ('esrp641728581','haw','1897-penal-laws'),
    ('esrp475081650','en','1869-penal-code'),
    ('esrp468790723','haw','1869-penal-code'),
    ('civilcodehawaii00armsgoog','en','1859-civil-code'),
    ('hekumukanawaiam00hawagoog','haw','1859-civil-code'),
    ('statutelawshism00ricogoog','en','1846-statute-laws'),
    ('kanawaiikauiaek00ricogoog','haw','1846-statute-laws'),
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

def stream(url, dest:Path):
    h=hashlib.sha256(); n=0
    dest.parent.mkdir(parents=True,exist_ok=True)
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=600) as r, dest.open('wb') as f:
        ct=r.headers.get('Content-Type',''); cl=r.headers.get('Content-Length')
        while True:
            buf=r.read(1<<20)
            if not buf: break
            f.write(buf); h.update(buf); n+=len(buf)
    return ct,cl,n,h.hexdigest()

def sha(b): return hashlib.sha256(b).hexdigest()
def now(): return dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

def main():
    manifest=[]
    # ToS
    for tag,url,fn in [
        ('ia_terms','https://archive.org/about/terms.php','ia_terms.html'),
    ]:
        try:
            st,ct,b=fetch(url)
            p=RAW/'_tos'/fn; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(b)
            manifest.append({'kind':'tos','tag':tag,'source_url':url,'local_path':str(p.relative_to(ROOT)),'fetched_at':now(),'http_status':st,'content_type':ct,'bytes':len(b),'sha256':sha(b),'mode':'tos'})
            print('tos',tag,len(b))
        except Exception as e:
            print('tos ERR',e)
        time.sleep(RATE)

    for item, side, pair in ITEMS:
        # IA metadata API
        meta_url=f'https://archive.org/metadata/{item}'
        try:
            st,ct,b=fetch(meta_url)
            (RAW/f'{item}__ia_metadata.json').write_bytes(b)
            md=json.loads(b)
            files={f['name']:f for f in md.get('files',[])}
            manifest.append({'kind':'ia_metadata','item_id':item,'side':side,'pair':pair,'source_url':meta_url,'local_path':f'data/raw/hawaiian-kingdom-statutes-paired-imprints/20260501/{item}__ia_metadata.json','fetched_at':now(),'http_status':st,'content_type':ct,'bytes':len(b),'sha256':sha(b),'mode':'metadata'})
        except Exception as e:
            print(item,'meta ERR',e); files={}
        time.sleep(RATE)

        # Determine derivative filenames
        # Find pdf, djvu.xml, hocr, meta.xml, marc.xml
        targets=[]
        for fname,info in files.items():
            if fname.endswith('.pdf') and 'Text PDF' in info.get('format',''):
                targets.append(('pdf',fname))
            elif fname.endswith('_djvu.xml'):
                targets.append(('djvu_xml',fname))
            elif fname.endswith('_hocr_searchtext.txt.gz'):
                targets.append(('hocr_searchtext',fname))
            elif fname.endswith('_meta.xml'):
                targets.append(('meta_xml',fname))
            elif fname.endswith('_marc.xml'):
                targets.append(('marc_xml',fname))

        for kind,fname in targets:
            url=f'https://archive.org/download/{item}/{fname}'
            dest=RAW/f'{item}__{fname}'
            try:
                ct,cl,n,h=stream(url,dest)
                manifest.append({'kind':kind,'item_id':item,'side':side,'pair':pair,'ia_filename':fname,'source_url':url,'local_path':str(dest.relative_to(ROOT)),'fetched_at':now(),'content_type':ct,'content_length_header':cl,'bytes':n,'sha256':h,'rights_note':'PD by US copyright term (pre-1929); sovereign-edicts doctrine for the legal text','mode':'full'})
                print(item,kind,n)
            except Exception as e:
                print(item,kind,'ERR',e)
                manifest.append({'kind':kind,'item_id':item,'error':str(e),'source_url':url,'fetched_at':now(),'mode':'failed'})
            time.sleep(RATE)

    # Existing _djvu.txt files: register in manifest with sha256
    print('registering existing _djvu.txt files...')
    for item,side,pair in ITEMS:
        for f in RAW.glob(f'{item}__*_djvu.txt'):
            b=f.read_bytes()
            manifest.append({'kind':'djvu_txt_existing','item_id':item,'side':side,'pair':pair,'local_path':str(f.relative_to(ROOT)),'fetched_at_pre':'2026-05-01T00:38Z (prior session via 208_fetch_hk_statutes_djvu.py)','bytes':len(b),'sha256':sha(b),'mode':'preexisting'})

    mfpath=RAW/'manifest_complete.jsonl'
    with mfpath.open('w') as f:
        for r in manifest: f.write(json.dumps(r,ensure_ascii=False)+'\n')

    summary={
        'source_id':'hawaiian-kingdom-statutes-paired-imprints',
        'source_name':'Hawaiian Kingdom statutes — bilingual paired imprints (1846/1859/1869/1897)',
        'fetch_date_utc':now(),
        'fetcher':'scripts/_frank_pull_hk_complete.py',
        'tos_url':'https://archive.org/about/terms.php',
        'rights_summary':'1846-1897 Hawaiian Kingdom government works. US public domain by copyright term (pre-1929). Sovereign-edicts doctrine applies to the legal text. archive.org redistributes scans + OCR; IA ToS governs the bytes only.',
        'rights_status':'public_domain',
        'release_eligible':False,'prototype_only':True,
        'paired_imprints':[
            {'pair':'1846-statute-laws','en_item':'statutelawshism00ricogoog','haw_item':'kanawaiikauiaek00ricogoog'},
            {'pair':'1859-civil-code','en_item':'civilcodehawaii00armsgoog','haw_item':'hekumukanawaiam00hawagoog'},
            {'pair':'1869-penal-code','en_item':'esrp475081650','haw_item':'esrp468790723'},
            {'pair':'1897-penal-laws','en_item':'esrp641724381','haw_item':'esrp641728581'},
        ],
        'counts':{
            'pdf_full':sum(1 for r in manifest if r.get('kind')=='pdf' and r.get('mode')=='full'),
            'djvu_xml':sum(1 for r in manifest if r.get('kind')=='djvu_xml' and r.get('mode')=='full'),
            'hocr_searchtext':sum(1 for r in manifest if r.get('kind')=='hocr_searchtext' and r.get('mode')=='full'),
            'meta_xml':sum(1 for r in manifest if r.get('kind')=='meta_xml' and r.get('mode')=='full'),
            'marc_xml':sum(1 for r in manifest if r.get('kind')=='marc_xml' and r.get('mode')=='full'),
            'ia_metadata':sum(1 for r in manifest if r.get('kind')=='ia_metadata' and r.get('mode')=='metadata'),
            'djvu_txt_preexisting':sum(1 for r in manifest if r.get('kind')=='djvu_txt_existing'),
            'failures':sum(1 for r in manifest if r.get('mode')=='failed'),
        },
    }
    (RAW/'manifest_summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary['counts'],indent=2))

if __name__=='__main__':
    main()
