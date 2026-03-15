def match_skills(candidate_skills):

    job_required_skills = [
        "python",
        "sql",
        "power bi",
        "excel",
        "machine learning"
    ]

    matched = []

    for skill in candidate_skills:
        if skill in job_required_skills:
            matched.append(skill)

    score = (len(matched) / len(job_required_skills)) * 100

    return score, matched