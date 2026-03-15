def extract_skills(text):

    skills_db = [
        "python","sql","excel","power bi","tableau","pandas",
        "numpy","machine learning","data analysis",
        "statistics","data visualization"
    ]

    text = text.lower()

    found_skills = []

    for skill in skills_db:
        if skill in text:
            found_skills.append(skill)

    return found_skills