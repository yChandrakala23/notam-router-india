"""Merged classifier: Q-code rules first, ML fallback for missing/ambiguous codes.

Owner: Person A.

    from classification.merged import classify
    result = classify(q_code="QRTCA", e_text="...")   # -> Classification

Decision order
1. Q-code present and unambiguous  -> rules (method RULES, confidence 1.0)
2. otherwise, if a trained model exists -> ML on E-text
   * confidence >= LOW_CONFIDENCE -> ML severity (method ML or RULES+ML)
   * else -> RESTRICTIVE (method ML_LOW_CONF_DEFAULT)
   * category: from the Q-code subject when known, else from ML
3. no model -> RESTRICTIVE / category from Q-code or OTHER (method DEFAULT)
4. keyword guard can raise severity (method KEYWORD_GUARD), never lower it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from classification.ml import LOW_CONFIDENCE, NotamTextModel, keyword_guard
from classification.rules import classify_qcode, more_severe

_MODEL_CACHE: dict[str, Optional[NotamTextModel]] = {}


@dataclass(frozen=True)
class Classification:
    category: str
    severity: str
    confidence: float
    method: str
    reason: str
    rule: Optional[str] = None            # Q-code rule that fired (stage 1)
    keyword: Optional[str] = None         # text span that triggered the keyword guard
    uncertainty: tuple = ()               # human-readable reasons to doubt the result
    probabilities: Optional[dict] = None  # ML class probabilities {field: {class: p}}

    def explain(self) -> dict:
        return {"category": self.category, "severity": self.severity,
                "confidence": self.confidence, "method": self.method, "reason": self.reason,
                "rule": self.rule, "keyword": self.keyword,
                "uncertainty": list(self.uncertainty), "probabilities": self.probabilities}


def default_model() -> Optional[NotamTextModel]:
    if "default" not in _MODEL_CACHE:
        try:
            _MODEL_CACHE["default"] = NotamTextModel.load()
        except Exception:  # corrupted / incompatible pickle -> rules only
            _MODEL_CACHE["default"] = None
    return _MODEL_CACHE["default"]


def classify(
    q_code: Optional[str],
    e_text: Optional[str],
    *,
    model: Optional[NotamTextModel] | str = "default",
    use_guard: bool = True,
    threshold: float = LOW_CONFIDENCE,
) -> Classification:
    if model == "default":
        model = default_model()

    rule = classify_qcode(q_code)
    if rule is not None and not rule.ambiguous:
        return Classification(rule.category, rule.severity, 1.0, "RULES", rule.reason, rule=rule.reason)

    uncertainty: list[str] = []
    if rule is not None:
        uncertainty.append(f"Q-code {q_code} is ambiguous: {rule.reason}")
    elif q_code:
        uncertainty.append(f"Q-code {q_code!r} not usable")
    else:
        uncertainty.append("no Q-code (e.g. AAI summary): decided from E-text only")
    known_category = rule.category if rule is not None and rule.category != "OTHER" else None
    probabilities = None
    category_conf = 0.0

    if model is not None and e_text:
        pred = model.predict([e_text])[0]
        try:
            probabilities = model.probabilities(e_text)
        except Exception:  # older pickles
            probabilities = None
        category = known_category or pred.category
        category_conf = pred.category_conf if not known_category else 1.0
        if not known_category and pred.category_conf < threshold:
            uncertainty.append(f"ML category {pred.category} has low probability ({pred.category_conf:.2f})")
        if pred.severity_conf >= threshold:
            severity, method = pred.severity, ("RULES+ML" if rule else "ML")
            reason = f"ML severity {pred.severity} (p={pred.severity_conf:.2f})"
        else:
            severity, method = "RESTRICTIVE", "ML_LOW_CONF_DEFAULT"
            reason = (f"ML low confidence (p={pred.severity_conf:.2f} < {threshold}); "
                      "defaulting to RESTRICTIVE")
            uncertainty.append(f"ML severity {pred.severity} below threshold {threshold}")
        confidence = pred.severity_conf
    else:
        category = known_category or "OTHER"
        severity, method, confidence = "RESTRICTIVE", "DEFAULT", 0.0
        reason = "no usable Q-code and no ML model; conservative RESTRICTIVE"
        uncertainty.append("no ML model available")

    keyword = None
    if use_guard:
        hit = keyword_guard(e_text)
        if hit and more_severe(hit.severity, severity) != severity:
            uncertainty.append(f"keyword guard raised severity {severity} -> {hit.severity} ('{hit.matched}')")
            severity = hit.severity
            keyword = hit.matched
            # Only replace the category when nothing better is known.
            if category == "OTHER" or (known_category is None and category_conf < threshold):
                category = hit.category
            elif category != hit.category:
                uncertainty.append(f"guard suggests category {hit.category}; kept {category}")
            method = "KEYWORD_GUARD"
            reason = f"E-text keyword guard: {hit.label}"

    return Classification(category, severity, round(float(confidence), 4), method, reason,
                          rule=rule.reason if rule else None, keyword=keyword,
                          uncertainty=tuple(uncertainty), probabilities=probabilities)
