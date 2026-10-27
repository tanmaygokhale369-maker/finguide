"""Optional local FinBERT inference; never downloads weights at runtime."""
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import os
import logging
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SentimentResult:
    label: str
    confidence: float | None
    model_version: str | None


class FinBERTAnalyzer:
    """Load FinBERT only from an explicitly configured local model directory."""
    def __init__(self, model_path: str | None = None):
        self.model_path = model_path or os.getenv("FINBERT_MODEL_PATH")
        self._pipeline = None
        self._pipeline_lock = Lock()
        self._load_failed = False

    def analyze(self, text: str) -> SentimentResult:
        model_dir = Path(self.model_path) if self.model_path else None
        if (
            not text.strip()
            or self._load_failed
            or model_dir is None
            or not (model_dir / "config.json").is_file()
        ):
            return SentimentResult("uncertain", None, None)
        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline
            if self._pipeline is None:
                with self._pipeline_lock:
                    if self._pipeline is None:
                        tokenizer = AutoTokenizer.from_pretrained(
                            self.model_path,
                            local_files_only=True,
                        )
                        model = AutoModelForSequenceClassification.from_pretrained(
                            self.model_path,
                            local_files_only=True,
                        )
                        self._pipeline = pipeline(
                            "text-classification",
                            model=model,
                            tokenizer=tokenizer,
                        )
            output = self._pipeline(text[:10000], top_k=1, truncation=True)[0]
            label = str(output["label"]).lower()
            if label not in {"positive", "negative", "neutral"}:
                return SentimentResult("uncertain", None, os.getenv("FINBERT_MODEL_VERSION", "local-finbert-unspecified"))
            score = float(output["score"])
            version = os.getenv("FINBERT_MODEL_VERSION", "local-finbert-unspecified")
            return SentimentResult(label if score >= 0.60 else "uncertain", score, version)
        except (ImportError, OSError, RuntimeError, KeyError, TypeError, ValueError) as exc:
            self._load_failed = True
            logger.warning("FinBERT unavailable (%s); sentiment remains uncertain.", type(exc).__name__)
            return SentimentResult("uncertain", None, os.getenv("FINBERT_MODEL_VERSION", "local-finbert-unspecified"))


@lru_cache(maxsize=1)
def get_sentiment_analyzer() -> FinBERTAnalyzer:
    """Reuse the lazy analyzer and its loaded model for this backend process."""
    return FinBERTAnalyzer()
