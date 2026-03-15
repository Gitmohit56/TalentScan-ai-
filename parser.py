from pdfminer.high_level import extract_text
import re

def extract_resume_text(file_path):

    text = extract_text(file_path)

    # remove (cid:xxx) characters
    text = re.sub(r'\(cid:\d+\)', ' ', text)

    # remove extra spaces
    text = re.sub(r'\s+', ' ', text)

    return text


def extract_email(text):
    if not text:
        return ""
    matches = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    return matches[0] if matches else ""
