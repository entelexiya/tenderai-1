"""Publish only reviewed application files. Uses local HF login, never inline tokens."""
import argparse
from pathlib import Path
from huggingface_hub import HfApi, CommitOperationAdd, CommitOperationDelete

ROOT=Path(__file__).resolve().parent.parent
FILES=['Dockerfile','README.md','index.html','styles.css','legacy.html','legacy.css','app.js','config.js','favicon.svg']
FILES += ['backend/'+p.name for p in (ROOT/'backend').iterdir() if p.is_file() and p.suffix in {'.py','.txt'}]
OLD=['main.py','predictor.py','extract_requirements.py','legal_compliance.py','winner_history.py','requirements.txt','model.pkl','scaler.pkl','backend/artifacts/model.pkl','backend/artifacts/scaler.pkl','backend/ml.py','backend/download_model.py','backend/requirements-ml.txt']

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--space',required=True); args=parser.parse_args()
    api=HfApi(); api.whoami()
    info=api.repo_info(args.space,repo_type='space'); existing=set(api.list_repo_files(args.space,repo_type='space',revision=info.sha))
    operations=[CommitOperationAdd(path_in_repo=name,path_or_fileobj=str(ROOT/name)) for name in FILES]
    operations += [CommitOperationDelete(path_in_repo=name) for name in OLD if name in existing]
    result=api.create_commit(args.space,repo_type='space',operations=operations,parent_commit=info.sha,commit_message='Rebuild TenderAI: evidence-based document review and new interface')
    print(result.commit_url)

if __name__=='__main__': main()
