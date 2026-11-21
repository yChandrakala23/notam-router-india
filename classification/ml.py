"""Stage 2 of the merged classifier: TF-IDF + logistic regression on E-text.

Owner: Person A.

Used only when the Q-code is missing (e.g. AAI summary records) or ambiguous
(QXXXX, condition XX).  Two independent models predict *category* and
*severity*.  A prediction below ``LOW_CONFIDENCE`` is replaced by RESTRICTIVE
(conservative default, methodology v2).

A small keyword guard runs alongside the model: the weak-label training data
contains almost no BLOCKING examples (they are rare in the corpus), so a model
alone cannot learn them.  Explicit phrases such as "ROCKET LAUNCH" or
"AD CLSD" raise the severity to BLOCKING.  The guard can only make a result
*more* severe, never less.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

MODEL_PATH = Path(__file__).resolve().parent / "models" / "notam_text_model.joblib"
LOW_CONFIDENCE = 0.55

_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def clean_text(text: Optional[str]) -> str:
    """Upper-case, collapse whitespace, map numbers to '#'."""
    if not text:
        return ""
    text = _NUMBER.sub("#", text.upper())
    return " ".join(text.split())


# (pattern, category, severity, label)
_GUARD_RULES = [
    (r"\bROCKET\b.*\bLAUNCH|\bLAUNCH\b.*\bROCKET|\bMISSILE\b|\bLIVE FIRING\b|\bFIRING\b.*\bRANGE",
     "NAV_WARNING", "BLOCKING", "rocket/missile/firing activity"),
    (r"\bNO FLT (?:IS )?PERMITTED\b|\bDNG ZONE\b|\bDANGER ZONE\b",
     "AIRSPACE_RESTRICTION", "BLOCKING", "flight not permitted / danger zone"),
    (r"\b(?:PROHIBITED|RESTRICTED|DANGER) AREA\b.*\bACT(?:IVATED|IVE)?\b|\bTEMPO(?:RARY)? RESTRICTED AREA\b",
     "AIRSPACE_RESTRICTION", "BLOCKING", "restricted/danger area active"),
    (r"\b(?:AD|AERODROME|AIRPORT|AIRFIELD) (?:IS )?(?:CLSD|CLOSED)\b|\bAIRFIELD CLOSURE\b|\bAD CLOSURE\b",
     "AERODROME", "BLOCKING", "aerodrome closed"),
    # Hazards the methodology lists as RESTRICTIVE (warning, not rejection).
    (r"\bUAS\b|\bRPAS\b|\bDRONES?\b|\bUNMANNED\b",
     "NAV_WARNING", "RESTRICTIVE", "unmanned aircraft activity"),
    (r"\bLASER\b", "NAV_WARNING", "RESTRICTIVE", "laser activity"),
    (r"\bAERIAL (?:ACT|ACTIVITY|DISPLAY)\b|\bPARA ?(?:CHUTE|JUMP|GLID)\w*|\bPJE\b|"
     r"\bBALLOON\b|\bAEROBATIC\w*",
     "NAV_WARNING", "RESTRICTIVE", "aerial activity / parachuting / balloon"),
    (r"\b(?:GNSS|GPS)\b.*\b(?:INTERFERENCE|JAMMING|SPOOFING|UNRELIABLE|LOSS)\b",
     "NAVAID_COMMS", "RESTRICTIVE", "GNSS interference"),
]
_GUARD_COMPILED = [(re.compile(p), c, s, l) for p, c, s, l in _GUARD_RULES]


@dataclass(frozen=True)
class GuardHit:
    category: str
    severity: str
    label: str
    matched: str = ""      # the text span that triggered the guard


# The same "no longer active" conditions that rules.py maps to ADVISORY
# (CD deactivated, CN cancelled, AK resumed normal ops, HQ operation cancelled).
_INACTIVE_TEXT = re.compile(
    r"\bDEACTIVATED\b|\bDE-ACTIVATED\b|\bCANCELLED\b|\bCNL\b|\bWILL NOT TAKE PLACE\b|"
    r"\bNOT ACTIVE\b|\bRESUMED NORMAL\b|\bOPS? RESUMED\b"
)


def keyword_guard(e_text: Optional[str]) -> Optional[GuardHit]:
    """Explicit hazard phrases that may only *raise* severity.

    Returns None when the text says the activity is deactivated / cancelled,
    so a "danger area deactivated" NOTAM is not escalated.
    """
    text = " ".join((e_text or "").upper().split())
    if _INACTIVE_TEXT.search(text):
        return None
    for pattern, category, severity, label in _GUARD_COMPILED:
        match = pattern.search(text)
        if match:
            return GuardHit(category, severity, label, match.group(0)[:80])
    return None


def model_config(C: float = 4.0) -> dict:
    """Hyper-parameters of the baseline pipeline (stored in model metadata)."""
    return {
        "features": "TF-IDF word 1-2-grams (sublinear, min_df=1) + char_wb 3-5-grams (sublinear, min_df=2)",
        "classifier": "LogisticRegression(class_weight='balanced', max_iter=5000)",
        "C": C,
        "text_normalisation": "upper case, numbers -> '#', whitespace collapsed (ml.clean_text)",
        "low_confidence_threshold": LOW_CONFIDENCE,
    }


def build_pipeline(C: float = 4.0, n_docs: int | None = None):
    """TF-IDF (word 1-2 grams + char 3-5 grams) -> logistic regression."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import FeatureUnion, Pipeline

    features = FeatureUnion([
        ("word", TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True,
                                 token_pattern=r"(?u)\b[A-Z#][A-Z#/]+\b", lowercase=False)),
        # min_df=2 drops one-off character n-grams; with very small training
        # sets (< 20 texts) that can remove every term, so use 1 there.
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5),
                                 min_df=2 if (n_docs or 0) >= 20 else 1,
                                 sublinear_tf=True, lowercase=False)),
    ])
    return Pipeline([
        ("features", features),
        ("clf", LogisticRegression(C=C, max_iter=5000, class_weight="balanced")),
    ])


@dataclass
class TextPrediction:
    category: str
    category_conf: float
    severity: str
    severity_conf: float


class NotamTextModel:
    """Pair of pipelines (category, severity) trained on weak labels."""

    def __init__(self, category_model=None, severity_model=None, meta: dict | None = None):
        self.category_model = category_model
        self.severity_model = severity_model
        self.meta = meta or {}

    @staticmethod
    def _fit_one(texts, labels, C):
        labels = list(labels)
        if len(set(labels)) < 2:
            return ("constant", labels[0])
        model = build_pipeline(C, n_docs=len(texts))
        model.fit(texts, labels)
        return model

    def fit(self, texts: Sequence[str], categories: Sequence[Optional[str]],
            severities: Sequence[Optional[str]], C: float = 4.0) -> "NotamTextModel":
        """Fit category and severity models independently.

        A None label means "no usable label for this field"; that row is left
        out of that field's model only.
        """
        cleaned = [clean_text(t) for t in texts]
        cat_rows = [(t, c) for t, c in zip(cleaned, categories) if c]
        sev_rows = [(t, s) for t, s in zip(cleaned, severities) if s]
        if not cat_rows or not sev_rows:
            raise ValueError("need at least one labelled example per field")
        self.category_model = self._fit_one([t for t, _ in cat_rows], [c for _, c in cat_rows], C)
        self.severity_model = self._fit_one([t for t, _ in sev_rows], [s for _, s in sev_rows], C)
        self.meta.setdefault("n_train", len(cleaned))
        self.meta.setdefault("n_train_category", len(cat_rows))
        self.meta.setdefault("n_train_severity", len(sev_rows))
        self.meta.setdefault("config", model_config(C))
        return self

    def probabilities(self, text: str) -> dict:
        """Class probabilities for both fields (explainability)."""
        cleaned = [clean_text(text)]
        out = {}
        for name, model in (("category", self.category_model), ("severity", self.severity_model)):
            if isinstance(model, tuple):
                out[name] = {str(model[1]): 1.0}
            else:
                out[name] = {str(c): round(float(p), 4)
                             for c, p in zip(model.classes_, model.predict_proba(cleaned)[0])}
        return out

    @staticmethod
    def _predict_one_model(model, cleaned):
        if isinstance(model, tuple) and model[0] == "constant":
            return [(str(model[1]), 1.0) for _ in cleaned]
        proba = model.predict_proba(cleaned)
        classes = model.classes_
        best = proba.argmax(axis=1)
        return [(str(classes[i]), float(p[i])) for i, p in zip(best, proba)]

    def predict(self, texts: Sequence[str]) -> list[TextPrediction]:
        cleaned = [clean_text(t) for t in texts]
        cats = self._predict_one_model(self.category_model, cleaned)
        sevs = self._predict_one_model(self.severity_model, cleaned)
        return [TextPrediction(c, cc, s, sc) for (c, cc), (s, sc) in zip(cats, sevs)]

    def save(self, path: Path = MODEL_PATH) -> Path:
        import joblib

        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"category": self.category_model, "severity": self.severity_model,
                     "meta": self.meta}, path)
        return path

    @classmethod
    def load(cls, path: Path = MODEL_PATH) -> Optional["NotamTextModel"]:
        if not Path(path).exists():
            return None
        import joblib

        data = joblib.load(path)
        return cls(data["category"], data["severity"], data.get("meta"))
