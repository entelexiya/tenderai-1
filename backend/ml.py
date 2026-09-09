"""Optional experimental model. Never silently substitutes for a failed model."""
import hashlib
import os
from pathlib import Path
import pickle
import threading
import warnings

ROOT = Path(__file__).resolve().parent
HASHES = {'model.pkl': '4b8b72e2eb7db12d5a215818062844080c94dede44b11319a8b0862147d0ed58', 'scaler.pkl': '48719279a3518b172162b2a5f57a36b4a490e5b8bec4c92b4792593d90ac7cd6'}


class ExperimentalModel:
    def __init__(self):
        self.enabled = os.getenv('ENABLE_ML', '0') == '1'
        self.ready = False
        self.lock = threading.Lock()

    def load(self):
        if not self.enabled:
            return
        from sentence_transformers import SentenceTransformer
        from sklearn.exceptions import InconsistentVersionWarning
        self.embedder = SentenceTransformer(os.getenv('EMBEDDER_PATH', str(ROOT / 'model_local')), local_files_only=True)
        with warnings.catch_warnings():
            warnings.simplefilter('error', InconsistentVersionWarning)
            for name, expected in HASHES.items():
                data = (ROOT / 'artifacts' / name).read_bytes()
                if hashlib.sha256(data).hexdigest() != expected:
                    raise ValueError('Model artifact checksum mismatch')
                setattr(self, name.split('.')[0], pickle.loads(data))
        self.ready = True

    def inspect(self, pages):
        if not self.enabled:
            return {'status': 'disabled', 'included_in_score': False}
        if not self.ready:
            raise RuntimeError('Model unavailable')
        # Token windows preserve the encoder's 128-token constraint across the document.
        chunks = []
        for page in pages:
            tokens = self.embedder.tokenizer.encode(page['text'], add_special_tokens=False)
            for start in range(0, len(tokens), 120):
                chunks.append(self.embedder.tokenizer.decode(tokens[start:start + 120]))
        if len(chunks) > 256:
            return {'status': 'skipped', 'included_in_score': False, 'note': 'ML-показатель не рассчитан: больше 256 фрагментов. Проверка правилами выполнена по всему извлечённому тексту.'}
        import numpy as np
        with self.lock:
            vectors = self.embedder.encode(chunks, batch_size=16, show_progress_bar=False)
            raw = -self.model.decision_function(vectors)
            values = np.clip(self.scaler.transform(raw.reshape(-1, 1)), 0, 1)
        return {'status': 'experimental', 'included_in_score': False, 'anomaly_index': round(float(values.mean()) * 100, 1), 'chunks': len(chunks), 'note': 'Средняя аномальность фрагментов относительно обучающей выборки. Разбиение на фрагменты изменяет метод расчёта; показатель не валидирован и не входит в приоритет проверки.'}
