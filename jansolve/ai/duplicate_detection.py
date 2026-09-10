"""
ai/duplicate_detection.py — Duplicate & Similar Problem Detection
Uses TF-IDF Vectorization and Cosine Similarity to detect similar civic issues.
"""

import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Default similarity threshold: 0.40 to capture semantic duplicates reliably
DEFAULT_THRESHOLD = 0.40


def preprocess(text):
    """Clean and standardize input text for vectorization."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def find_similar_problems(new_title, new_description, existing_problems, threshold=DEFAULT_THRESHOLD):
    """Find problems in the database with high semantic similarity to the new submission.
    
    Args:
        new_title (str): Title of the new problem
        new_description (str): Description of the new problem
        existing_problems (list of dict or sqlite3.Row): List of problems with 'id', 'title', 'description', 'location'
        threshold (float): Minimum cosine similarity to flag (0.0 to 1.0)
        
    Returns:
        list of dict: Matched similar problems with similarity percentage
    """
    if not existing_problems:
        return []

    new_text = preprocess(f"{new_title} {new_description}")
    if not new_text:
        return []

    corpus = [new_text]
    valid_candidates = []

    for p in existing_problems:
        p_title = p['title'] if isinstance(p, dict) or hasattr(p, '__getitem__') else getattr(p, 'title', '')
        p_desc = p['description'] if isinstance(p, dict) or hasattr(p, '__getitem__') else getattr(p, 'description', '')
        p_text = preprocess(f"{p_title} {p_desc}")
        if p_text:
            corpus.append(p_text)
            valid_candidates.append(p)

    if not valid_candidates:
        return []

    # Build TF-IDF representations
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words='english', min_df=1)
    try:
        tfidf_matrix = vectorizer.fit_transform(corpus)
    except ValueError:
        return []

    # Compute cosine similarity between the query (index 0) and all existing items (index 1 to N)
    query_vector = tfidf_matrix[0:1]
    candidate_vectors = tfidf_matrix[1:]
    similarities = cosine_similarity(query_vector, candidate_vectors)[0]

    matches = []
    for idx, score in enumerate(similarities):
        score_val = float(score)
        if score_val >= threshold:
            candidate = valid_candidates[idx]
            matches.append({
                'id': candidate['id'],
                'title': candidate['title'],
                'description': candidate['description'],
                'location': candidate['location'] if 'location' in candidate.keys() else '',
                'category': candidate['category'] if 'category' in candidate.keys() else '',
                'support_count': candidate['support_count'] if 'support_count' in candidate.keys() else 0,
                'status': candidate['status'] if 'status' in candidate.keys() else 'REPORTED',
                'similarity_score': round(score_val, 2),
                'similarity_percent': int(round(score_val * 100))
            })

    # Sort by highest similarity first
    matches.sort(key=lambda x: x['similarity_score'], reverse=True)
    return matches
