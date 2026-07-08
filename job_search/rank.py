import re

SKILLS_VOCAB = [
    "python", "sql", "excel", "power bi", "tableau", "r", "sas", "spss",
    "machine learning", "statistics", "statistical", "xgboost", "regression",
    "data visualization", "etl", "data pipeline", "a/b testing",
    "hypothesis testing", "pandas", "numpy", "scikit-learn", "azure", "aws",
    "gcp", "snowflake", "data warehouse", "database", "dashboard",
    "forecasting", "clustering", "nlp", "deep learning", "tensorflow",
    "pytorch", "git", "vba", "looker", "power query", "dax", "monte carlo",
    "anova", "logistic regression",
]

FIT_THRESHOLD = 0.30


def extract_skills(text: str) -> set[str]:
    lowered = text.lower()
    return {kw for kw in SKILLS_VOCAB if re.search(r'\b' + re.escape(kw) + r'\b', lowered)}


def fit_score(posting_text: str, profile_text: str) -> float:
    posting_skills = extract_skills(posting_text)
    if not posting_skills:
        return 0.0
    profile_skills = extract_skills(profile_text)
    matched = posting_skills & profile_skills
    return len(matched) / len(posting_skills)


def passes_threshold(score: float) -> bool:
    return score >= FIT_THRESHOLD
