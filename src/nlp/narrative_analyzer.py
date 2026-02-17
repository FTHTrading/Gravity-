"""
Narrative Structure & NLP Analysis Module.

Identifies:
  - Storytelling patterns (hero/whistleblower/disappearance arcs)
  - Linguistic markers (urgency language, appeal-to-authority, etc.)
  - Cross-post textual similarity
  - Sentiment / emotional loading indicators
  - Template-based vs organic post detection

Uses only open-source NLP (no external API keys required).
"""

import json
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from src.database import insert_row, query_rows
from src.logger import get_logger

log = get_logger(__name__)

try:
    import nltk
    from nltk.tokenize import sent_tokenize, word_tokenize
    from nltk.corpus import stopwords
except ImportError:
    nltk = None
    log.warning("NLTK not installed; NLP features will be limited.")

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except ImportError:
    TfidfVectorizer = None
    log.warning("scikit-learn not installed; similarity analysis unavailable.")


# ── Narrative Pattern Definitions ────────────────────────────────────────────

NARRATIVE_PATTERNS = {
    "whistleblower": {
        "keywords": [
            "leaked", "whistleblower", "insider", "cover-up", "coverup",
            "suppressed", "censored", "silenced", "they don't want you to know",
            "hidden truth", "classified", "exposed",
        ],
        "description": "Whistleblower / insider revelation narrative",
    },
    "disappearance": {
        "keywords": [
            "disappeared", "missing", "vanished", "gone", "last seen",
            "no trace", "silenced", "taken", "abducted", "erased",
        ],
        "description": "Mysterious disappearance narrative",
    },
    "countdown_urgency": {
        "keywords": [
            "days left", "time is running out", "before it's too late",
            "happening soon", "mark your calendar", "prepare",
            "august 12", "get ready", "warning",
        ],
        "description": "Countdown / urgency narrative",
    },
    "authority_appeal": {
        "keywords": [
            "nasa", "scientist", "professor", "phd", "doctor",
            "peer-reviewed", "study shows", "research proves",
            "government", "pentagon", "classified document",
        ],
        "description": "Appeal to authority / institutional credibility",
    },
    "conspiracy_framing": {
        "keywords": [
            "they", "elites", "powers that be", "mainstream media",
            "what they're hiding", "wake up", "sheep", "red pill",
            "open your eyes", "do your own research",
        ],
        "description": "Conspiracy theory framing patterns",
    },
}


class NarrativeAnalyzer:
    """Analyze text collections for narrative structure and linguistic patterns."""

    def __init__(self):
        self._ensure_nltk_data()

    @staticmethod
    def _ensure_nltk_data():
        if nltk:
            for resource in ["punkt", "punkt_tab", "stopwords", "averaged_perceptron_tagger", "averaged_perceptron_tagger_eng"]:
                try:
                    nltk.data.find(f"tokenizers/{resource}" if "punkt" in resource else f"corpora/{resource}" if resource == "stopwords" else f"taggers/{resource}")
                except LookupError:
                    try:
                        nltk.download(resource, quiet=True)
                    except Exception:
                        pass

    # ── Pattern Detection ────────────────────────────────────────────────
    def detect_patterns(self, text: str, source_id: int | None = None) -> list[dict]:
        """
        Scan text for known narrative pattern keywords.
        Returns list of detected patterns with match counts.
        """
        text_lower = text.lower()
        detected = []

        for pattern_name, pattern_def in NARRATIVE_PATTERNS.items():
            matches = []
            for kw in pattern_def["keywords"]:
                count = text_lower.count(kw.lower())
                if count > 0:
                    matches.append({"keyword": kw, "count": count})

            if matches:
                total = sum(m["count"] for m in matches)
                result = {
                    "pattern_type": "narrative",
                    "pattern_label": pattern_name,
                    "confidence": min(total / 10.0, 1.0),  # simple heuristic
                    "detail_json": json.dumps({
                        "description": pattern_def["description"],
                        "matches": matches,
                        "total_hits": total,
                    }),
                    "analyzed_at": datetime.now(timezone.utc).isoformat(),
                }
                if source_id is not None:
                    result["source_id"] = source_id
                insert_row("narrative_patterns", result)
                detected.append(result)

        log.info("Detected %d narrative patterns", len(detected))
        return detected

    # ── Linguistic Feature Extraction ────────────────────────────────────
    def extract_linguistic_features(self, text: str) -> dict[str, Any]:
        """Extract quantitative linguistic features from text."""
        features: dict[str, Any] = {}

        sentences = sent_tokenize(text) if nltk else text.split(".")
        words = word_tokenize(text) if nltk else text.split()

        features["sentence_count"] = len(sentences)
        features["word_count"] = len(words)
        features["avg_sentence_length"] = (
            len(words) / len(sentences) if sentences else 0
        )

        # Exclamation / question density
        features["exclamation_count"] = text.count("!")
        features["question_count"] = text.count("?")
        features["caps_word_count"] = sum(1 for w in words if w.isupper() and len(w) > 1)

        # URL density
        urls = re.findall(r"https?://\S+", text)
        features["url_count"] = len(urls)

        # Unique word ratio (lexical diversity)
        if words:
            features["lexical_diversity"] = round(len(set(w.lower() for w in words)) / len(words), 3)

        return features

    # ── Cross-Post Similarity ────────────────────────────────────────────
    def compute_similarity_matrix(self, texts: list[str]) -> list[list[float]] | None:
        """
        Compute pairwise TF-IDF cosine similarity between provided texts.
        Useful for detecting copy-paste or template-based viral posts.
        """
        if TfidfVectorizer is None or len(texts) < 2:
            log.warning("Cannot compute similarity (need sklearn and >= 2 texts).")
            return None

        vectorizer = TfidfVectorizer(stop_words="english", max_features=5000)
        tfidf = vectorizer.fit_transform(texts)
        sim_matrix = cosine_similarity(tfidf).tolist()

        log.info("Similarity matrix computed for %d texts", len(texts))
        return sim_matrix

    def find_near_duplicates(self, texts: list[str], threshold: float = 0.8) -> list[tuple[int, int, float]]:
        """Return pairs of text indices with similarity above threshold."""
        matrix = self.compute_similarity_matrix(texts)
        if matrix is None:
            return []

        pairs = []
        for i in range(len(matrix)):
            for j in range(i + 1, len(matrix)):
                if matrix[i][j] >= threshold:
                    pairs.append((i, j, round(matrix[i][j], 4)))

        log.info("Found %d near-duplicate pairs (threshold=%.2f)", len(pairs), threshold)
        return pairs

    # ── Keyword Frequency Analysis ───────────────────────────────────────
    def keyword_frequency(self, text: str, top_n: int = 30) -> list[tuple[str, int]]:
        """Return most common non-stopword tokens."""
        words = word_tokenize(text.lower()) if nltk else text.lower().split()
        stop = set(stopwords.words("english")) if nltk else set()
        filtered = [w for w in words if w.isalpha() and w not in stop and len(w) > 2]
        return Counter(filtered).most_common(top_n)

    # ── Batch Analysis from Database ─────────────────────────────────────
    def analyze_all_posts(self) -> dict[str, Any]:
        """Run analysis on all social_posts currently in the database."""
        posts = query_rows("social_posts")
        if not posts:
            log.warning("No posts in database to analyze.")
            return {"status": "no_data"}

        texts = [p["post_text"] for p in posts if p.get("post_text")]
        all_patterns = []

        for post in posts:
            if post.get("post_text"):
                patterns = self.detect_patterns(post["post_text"], source_id=post["id"])
                all_patterns.extend(patterns)

        duplicates = self.find_near_duplicates(texts)
        combined_text = " ".join(texts)
        keywords = self.keyword_frequency(combined_text)
        features = self.extract_linguistic_features(combined_text)

        report = {
            "total_posts_analyzed": len(texts),
            "narrative_patterns_detected": len(all_patterns),
            "near_duplicate_pairs": len(duplicates),
            "top_keywords": keywords,
            "aggregate_features": features,
            "pattern_summary": Counter(p["pattern_label"] for p in all_patterns),
        }

        log.info("Batch NLP analysis complete: %d posts", len(texts))
        return report
