# tests/test_rank.py
from job_search.rank import extract_skills, fit_score, passes_threshold, FIT_THRESHOLD


def test_extract_skills_case_insensitive():
    skills = extract_skills("We need someone strong in SQL, Python, and Power BI.")
    assert "sql" in skills
    assert "python" in skills
    assert "power bi" in skills
    assert "tableau" not in skills


def test_fit_score_half_overlap():
    posting = "Requires SQL, Python, Tableau, and AWS experience."
    profile = "I have used SQL and Python extensively in my internship."
    score = fit_score(posting, profile)
    assert score == 0.5  # 2 of 4 posting skills (sql, python) are in profile


def test_fit_score_zero_when_no_skills_in_posting():
    assert fit_score("Great company culture and free snacks.", "SQL Python") == 0.0


def test_fit_score_full_overlap():
    posting = "SQL and Python required."
    profile = "SQL, Python, machine learning, statistics."
    assert fit_score(posting, profile) == 1.0


def test_passes_threshold_boundary_is_inclusive():
    assert FIT_THRESHOLD == 0.30
    assert passes_threshold(0.30) is True
    assert passes_threshold(0.29) is False
    assert passes_threshold(0.31) is True
