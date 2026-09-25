"""Level-2 / Level-3 ML components.

`SafetyClassifier` is the abstraction; `TfidfLogRegClassifier` is the working local
implementation. `TransformerSafetyClassifier` is an optional drop-in (DistilBERT or
similar via HuggingFace) that is only used when `transformers` + `torch` are installed
AND a fine-tuned model directory exists. Otherwise the system falls back to the
deterministic engine + classical ML. No external API is ever called.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import numpy as np

from app.nlp.normalize import normalize_for_model


def build_model_text(report: dict[str, Any]) -> str:
    parts = [normalize_for_model(report.get("description") or "")]
    if report.get("activity"):
        parts.append("activity " + normalize_for_model(str(report["activity"])))
    if report.get("report_type"):
        parts.append("rtype_" + str(report["report_type"]).lower().replace(" ", "_"))
    if report.get("injury_severity"):
        parts.append("injury_" + str(report["injury_severity"]).lower().replace(" ", "_"))
    return " ".join(parts)


class SafetyClassifier(ABC):
    """Binary SIF-potential classifier. predict_proba returns P(SIF potential)."""

    name: str = "abstract"
    version: str = "0"

    @abstractmethod
    def fit(self, texts: list[str], labels: list[int]) -> "SafetyClassifier": ...

    @abstractmethod
    def predict_proba(self, texts: list[str]) -> np.ndarray: ...

    def explain(self, text: str, top_k: int = 6) -> list[dict[str, Any]]:
        return []

    @abstractmethod
    def save(self, directory: str | Path) -> str: ...

    @classmethod
    @abstractmethod
    def load(cls, path: str | Path) -> "SafetyClassifier": ...


class TfidfLogRegClassifier(SafetyClassifier):
    name = "tfidf-logreg"

    def __init__(self, version: str = "clf-tfidf-lr-0", C: float = 2.0):
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression

        self.version = version
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1, max_features=8000)
        self.model = LogisticRegression(C=C, class_weight="balanced", max_iter=2000)
        self.params = {"ngram_range": [1, 2], "sublinear_tf": True, "C": C, "class_weight": "balanced", "max_features": 8000}

    def fit(self, texts: list[str], labels: list[int]) -> "TfidfLogRegClassifier":
        X = self.vectorizer.fit_transform(texts)
        self.model.fit(X, labels)
        return self

    def predict_proba(self, texts: list[str]) -> np.ndarray:
        X = self.vectorizer.transform(texts)
        return self.model.predict_proba(X)[:, 1]

    def explain(self, text: str, top_k: int = 6) -> list[dict[str, Any]]:
        x = self.vectorizer.transform([text])
        coefs = self.model.coef_[0]
        vocab = self.vectorizer.get_feature_names_out()
        contrib = [(vocab[i], float(x[0, i] * coefs[i])) for i in x.nonzero()[1]]
        contrib.sort(key=lambda t: -abs(t[1]))
        return [{"term": t, "weight": round(w, 4)} for t, w in contrib[:top_k]]

    def save(self, directory: str | Path) -> str:
        import joblib

        Path(directory).mkdir(parents=True, exist_ok=True)
        path = str(Path(directory) / f"{self.version}.joblib")
        joblib.dump({"version": self.version, "vectorizer": self.vectorizer, "model": self.model, "params": self.params}, path)
        return path

    @classmethod
    def load(cls, path: str | Path) -> "TfidfLogRegClassifier":
        import joblib

        data = joblib.load(path)
        obj = cls.__new__(cls)
        obj.version = data["version"]
        obj.vectorizer = data["vectorizer"]
        obj.model = data["model"]
        obj.params = data.get("params", {})
        return obj


class TransformerSafetyClassifier(SafetyClassifier):  # pragma: no cover - optional dependency
    """Optional HuggingFace sequence classifier (e.g. distilbert-base-uncased fine-tuned).

    Requires `pip install -r requirements-transformer.txt` and a local model directory
    at MODEL_PATH/transformer. Never downloads at request time; never calls an API.
    """

    name = "transformer"

    def __init__(self, model_dir: str | Path, version: str = "clf-transformer-0"):
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.version = version
        self.model_dir = str(model_dir)
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_dir, local_files_only=True)
        self.model = AutoModelForSequenceClassification.from_pretrained(self.model_dir, local_files_only=True)
        self.model.eval()

    @staticmethod
    def available(model_dir: str | Path) -> bool:
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401
        except Exception:
            return False
        return (Path(model_dir) / "config.json").exists()

    def fit(self, texts: list[str], labels: list[int]) -> "TransformerSafetyClassifier":
        raise NotImplementedError("Fine-tune offline with scripts/train_transformer.py; inference only at runtime.")

    def predict_proba(self, texts: list[str]) -> np.ndarray:
        import torch

        with torch.no_grad():
            enc = self.tokenizer(texts, truncation=True, padding=True, max_length=256, return_tensors="pt")
            logits = self.model(**enc).logits
            return torch.softmax(logits, dim=-1)[:, 1].cpu().numpy()

    def save(self, directory: str | Path) -> str:
        self.model.save_pretrained(directory)
        self.tokenizer.save_pretrained(directory)
        return str(directory)

    @classmethod
    def load(cls, path: str | Path) -> "TransformerSafetyClassifier":
        return cls(path)


def load_classifier(model_dir: str, artifact_path: str | None) -> SafetyClassifier | None:
    """Prefer an installed transformer model, else the active TF-IDF model, else None."""
    tdir = Path(model_dir) / "transformer"
    if os.environ.get("USE_TRANSFORMER", "false").lower() == "true" and TransformerSafetyClassifier.available(tdir):
        try:
            return TransformerSafetyClassifier(tdir)
        except Exception:
            pass
    if artifact_path and Path(artifact_path).exists():
        try:
            return TfidfLogRegClassifier.load(artifact_path)
        except Exception:
            return None
    return None


class LSAEmbedder:
    """Local sentence embedding: TF-IDF -> TruncatedSVD (latent semantic analysis).

    Produces fixed 64-d unit vectors stored in pgvector for similar-report search.
    """

    def __init__(self, dim: int = 64, version: str = "emb-lsa-0"):
        self.dim = dim
        self.version = version
        self.vectorizer = None
        self.svd = None

    def fit(self, texts: list[str]) -> "LSAEmbedder":
        from sklearn.decomposition import TruncatedSVD
        from sklearn.feature_extraction.text import TfidfVectorizer

        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1)
        X = self.vectorizer.fit_transform(texts)
        n_comp = max(1, min(self.dim, X.shape[0] - 1, X.shape[1] - 1))
        self.svd = TruncatedSVD(n_components=n_comp, random_state=0).fit(X)
        return self

    def embed(self, texts: list[str]) -> np.ndarray:
        assert self.vectorizer is not None and self.svd is not None
        Z = self.svd.transform(self.vectorizer.transform(texts))
        if Z.shape[1] < self.dim:
            Z = np.hstack([Z, np.zeros((Z.shape[0], self.dim - Z.shape[1]))])
        norms = np.linalg.norm(Z, axis=1, keepdims=True)
        norms[norms == 0] = 1
        return Z / norms

    def save(self, directory: str | Path) -> str:
        import joblib

        Path(directory).mkdir(parents=True, exist_ok=True)
        path = str(Path(directory) / f"{self.version}.joblib")
        joblib.dump(self, path)
        return path

    @staticmethod
    def load(path: str | Path) -> "LSAEmbedder":
        import joblib

        return joblib.load(path)
