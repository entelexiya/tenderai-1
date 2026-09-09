"""Evaluate expert category labels. Synthetic regression checks are not quality evidence.

Input JSONL: {"id":"...", "text":"...", "expected_categories":["brand", ...]}
Keep this independently labelled dataset outside the repository if confidential.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from backend.analysis import analyze, POINTS, VERSION


def main():
    parser=argparse.ArgumentParser();parser.add_argument('dataset');parser.add_argument('--output',required=True);args=parser.parse_args()
    counts={k:{'tp':0,'fp':0,'fn':0,'tn':0} for k in POINTS}
    seen=set(); documents=0
    for line in Path(args.dataset).read_text(encoding='utf-8-sig').splitlines():
        if not line.strip(): continue
        row=json.loads(line); expected=set(row['expected_categories'])
        if expected-set(POINTS): raise ValueError('Unknown category label')
        fingerprint=hashlib.sha256(row['text'].encode()).hexdigest()
        if fingerprint in seen: raise ValueError('Duplicate text in evaluation dataset')
        seen.add(fingerprint)
        report=analyze([{'number':1,'text':row['text']}]); actual={f['category'] for f in report['findings']}
        for k,c in counts.items():
            c['tp' if k in actual and k in expected else 'fp' if k in actual else 'fn' if k in expected else 'tn']+=1
        documents+=1
    if not documents: raise ValueError('Empty dataset')
    for c in counts.values():
        c['precision']=c['tp']/(c['tp']+c['fp']) if c['tp']+c['fp'] else None
        c['recall']=c['tp']/(c['tp']+c['fn']) if c['tp']+c['fn'] else None
    output={'version':VERSION,'documents':documents,'dataset_sha256':hashlib.sha256(Path(args.dataset).read_bytes()).hexdigest(),'categories':counts,'note':'Document-level category metrics. This does not measure legal correctness or quote/page accuracy. Verify independent expert annotation and separation from training data.'}
    Path(args.output).write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Evaluated {documents} documents. Report: {args.output}')

if __name__=='__main__':main()
