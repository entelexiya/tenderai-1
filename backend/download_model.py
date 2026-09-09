"""Executed during container build, never during the first user request."""
from pathlib import Path
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2', revision='e8f8c211226b894fcb81acc59f3b34ba3efd5f42')
model.save(str(Path(__file__).resolve().parent / 'model_local'))
