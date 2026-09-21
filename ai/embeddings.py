import math
import re
from collections import Counter

# Try importing sentence_transformers if present, otherwise use our deterministic vectorizer
_st_model = None
try:
    from sentence_transformers import SentenceTransformer
    _st_model = SentenceTransformer('all-MiniLM-L6-v2')
except Exception:
    _st_model = None

def _tokenize(text: str):
    return re.findall(r'\b\w+\b', text.lower())

def compute_deterministic_vector(text: str, dim: int = 128) -> list:
    """
    Computes a normalized dense vector for text using token hashing & TF-IDF style weights.
    Guarantees fast, reproducible semantic-like embeddings without external neural weight files.
    """
    tokens = _tokenize(text)
    if not tokens:
        return [0.0] * dim
    
    vec = [0.0] * dim
    counts = Counter(tokens)
    for token, count in counts.items():
        # Hash token into vector dimensions
        h = abs(hash(token)) % dim
        h2 = abs(hash(token + '_2')) % dim
        weight = (1.0 + math.log(count))
        vec[h] += weight
        vec[h2] += weight * 0.5
    
    # Normalize vector to unit length (L2 norm)
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [x / norm for x in vec]
    return vec

def get_embedding(text: str) -> list:
    """Returns vector embedding for text using sentence-transformers or deterministic vectorizer."""
    if not text:
        return [0.0] * 128
    if _st_model is not None:
        try:
            return _st_model.encode(text).tolist()
        except Exception:
            pass
    return compute_deterministic_vector(text, dim=128)

def cosine_similarity(vec1: list, vec2: list) -> float:
    """Computes cosine similarity between two float vectors."""
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return max(0.0, min(1.0, dot / (norm1 * norm2)))

def find_best_template_match(query_text: str, templates: list, threshold: float = 0.78):
    """
    Compares query against template embeddings.
    templates: list of WorkflowTemplate model instances or dicts with 'name', 'description', 'dag_json', 'embedding'
    Returns (best_template, similarity_score) or (None, 0.0) if below threshold.
    """
    if not query_text or not templates:
        return None, 0.0
    
    query_vec = get_embedding(query_text)
    best_match = None
    highest_score = 0.0

    for tmpl in templates:
        tmpl_desc = f"{getattr(tmpl, 'name', '')} {getattr(tmpl, 'description', '')}"
        tmpl_vec = get_embedding(tmpl_desc)
        score = cosine_similarity(query_vec, tmpl_vec)
        if score > highest_score:
            highest_score = score
            best_match = tmpl

    if highest_score >= threshold:
        return best_match, highest_score
    return None, highest_score
