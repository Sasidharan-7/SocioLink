"""
ai/expert_matching.py — AI Expert & University Matching
Uses NLP, TF-IDF Vectorization, and Cosine Similarity to pair societal problems
with the most qualified academic faculties, student researchers, and industry experts.
"""

import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def preprocess(text):
    """Clean and normalize text."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def match_experts_for_problem(problem_title, problem_description, problem_category, experts_list, top_n=5):
    """Match a societal problem description to available experts/institutions using Cosine Similarity.
    
    Args:
        problem_title (str): Title of problem
        problem_description (str): Full text of problem
        problem_category (str): Category (e.g., 'Water & Sanitation')
        experts_list (list of dict or sqlite3.Row): Experts from database
        top_n (int): Maximum number of recommendations to return
        
    Returns:
        list of dict: Ranked expert recommendations with match percentage
    """
    if not experts_list:
        return []

    problem_corpus = preprocess(f"{problem_title} {problem_description} {problem_category} {problem_category}")
    if not problem_corpus:
        return []

    corpus = [problem_corpus]
    valid_experts = []

    for exp in experts_list:
        skills = exp['skills'] if exp['skills'] else ''
        expertise = exp['expertise_area'] if 'expertise_area' in exp.keys() and exp['expertise_area'] else ''
        dept = exp['department'] if 'department' in exp.keys() and exp['department'] else ''
        org = exp['organization'] if 'organization' in exp.keys() and exp['organization'] else ''
        kws = exp['match_keywords'] if 'match_keywords' in exp.keys() and exp['match_keywords'] else ''

        exp_text = preprocess(f"{skills} {skills} {expertise} {dept} {org} {kws}")
        corpus.append(exp_text or "general engineering research")
        valid_experts.append(exp)

    if not valid_experts:
        return []

    # Vectorize problem text + expert skills
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words='english', min_df=1)
    try:
        tfidf_matrix = vectorizer.fit_transform(corpus)
    except ValueError:
        return []

    query_vec = tfidf_matrix[0:1]
    expert_vecs = tfidf_matrix[1:]
    similarities = cosine_similarity(query_vec, expert_vecs)[0]

    matched_results = []
    for idx, raw_score in enumerate(similarities):
        score = float(raw_score)
        # Rescale match score gracefully for public dashboard presentation
        if score > 0.05:
            # Scaled match percentage between 65% and 96%
            match_percent = int(min(96, max(60, round(score * 80 + 35))))
        else:
            match_percent = int(min(55, max(30, round(score * 100 + 30))))

        exp_data = valid_experts[idx]
        matched_results.append({
            'id': exp_data['id'],
            'name': exp_data['name'],
            'organization': exp_data['organization'] or 'Independent Expert',
            'department': exp_data['department'] or (exp_data['expertise_area'] if 'expertise_area' in exp_data.keys() else 'Domain Specialist'),
            'skills': exp_data['skills'] or 'Engineering & Problem Solving',
            'raw_score': score,
            'match_percent': match_percent
        })

    # Sort descending by match percentage
    matched_results.sort(key=lambda x: x['match_percent'], reverse=True)
    return matched_results[:top_n]
