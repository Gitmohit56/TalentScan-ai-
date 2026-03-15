from flask import Flask, render_template, request, redirect, send_file, abort, Response
import os
import uuid
import zipfile
import csv
import io

from werkzeug.utils import secure_filename

from resume_parser.parser import extract_resume_text, extract_email
from jd_matching.skills import extract_skills
from jd_matching.matcher import match_skills

from models.database import cursor, conn

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {".pdf", ".zip"}

# create uploads folder
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


def _is_allowed(filename):
    _, ext = os.path.splitext(filename)
    return ext.lower() in ALLOWED_EXTENSIONS


def _score_and_store(resume_path):
    resume_text = extract_resume_text(resume_path)
    email = extract_email(resume_text)
    skills = extract_skills(resume_text)
    score, matched = match_skills(skills)

    if score >= 70:
        status = "Shortlisted"
    elif score >= 50:
        status = "Needs Review"
    else:
        status = "Rejected"

    rel_path = os.path.relpath(resume_path, app.config["UPLOAD_FOLDER"])
    cursor.execute(
        "INSERT INTO candidates(skills, matched, score, status, resume_path, email) VALUES(?,?,?,?,?,?)",
        (str(skills), str(matched), score, status, rel_path, email)
    )
    conn.commit()


# ---------------- Home Page ----------------
@app.route("/")
def home():
    return render_template("index.html")


# ---------------- Upload Resume ----------------
@app.route("/upload", methods=["POST"])
def upload():

    files = request.files.getlist("resume")

    if not files:
        return "No file uploaded"

    processed = 0

    for file in files:
        if not file or file.filename == "":
            continue

        if not _is_allowed(file.filename):
            continue

        ext = os.path.splitext(file.filename)[1].lower()

        if ext == ".zip":
            zip_name = secure_filename(file.filename)
            zip_path = os.path.join(app.config["UPLOAD_FOLDER"], zip_name)
            file.save(zip_path)

            extract_dir = os.path.join(app.config["UPLOAD_FOLDER"], f"zip_{uuid.uuid4().hex}")
            os.makedirs(extract_dir, exist_ok=True)

            with zipfile.ZipFile(zip_path, "r") as zf:
                for member in zf.namelist():
                    if not member.lower().endswith(".pdf"):
                        continue
                    base_name = os.path.basename(member)
                    if not base_name:
                        continue
                    safe_name = secure_filename(base_name)
                    target_path = os.path.join(extract_dir, safe_name)
                    with zf.open(member) as source, open(target_path, "wb") as dest:
                        dest.write(source.read())
                    _score_and_store(target_path)
                    processed += 1
        else:
            safe_name = secure_filename(file.filename)
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], safe_name)
            file.save(filepath)
            _score_and_store(filepath)
            processed += 1

    if processed == 0:
        return "No valid files found. Please upload PDF or ZIP (containing PDFs)."

    return redirect("/dashboard")


# ---------------- Dashboard ----------------
@app.route("/dashboard")
def dashboard():

    cursor.execute("SELECT * FROM candidates")
    all_candidates = cursor.fetchall()

    total = len(all_candidates)

    shortlisted = len([c for c in all_candidates if c[4] == "Shortlisted"])
    rejected = len([c for c in all_candidates if c[4] == "Rejected"])
    review = len([c for c in all_candidates if c[4] == "Needs Review"])

    status_filter = request.args.get("status", "").strip()
    search = request.args.get("search", "").strip().lower()

    candidates = list(all_candidates)

    if status_filter:
        if status_filter.lower() == "review":
            status_filter = "Needs Review"
        candidates = [c for c in candidates if c[4] == status_filter]

    if search:
        candidates = [c for c in candidates if search in (c[1] or "").lower()]

    overall_avg = sum([c[3] for c in all_candidates]) / total if total > 0 else 0

    return render_template(
        "dashboard.html",
        candidates=candidates,
        total=total,
        shortlisted=shortlisted,
        rejected=rejected,
        review=review,
        avg_score=int(overall_avg),
        status_filter=status_filter,
        search=search
    )


# ---------------- Candidates Page ----------------
@app.route("/candidates")
def candidates():

    sort = request.args.get("sort", "score")
    direction = request.args.get("dir", "desc")
    status_filter = request.args.get("status", "").strip()
    search = request.args.get("search", "").strip().lower()

    sort_map = {
        "score": "score",
        "status": "status",
        "id": "id"
    }
    sort_col = sort_map.get(sort, "score")
    sort_dir = "ASC" if direction == "asc" else "DESC"

    query = "SELECT * FROM candidates"
    params = []

    if status_filter:
        if status_filter.lower() == "review":
            status_filter = "Needs Review"
        query += " WHERE status = ?"
        params.append(status_filter)

    query += f" ORDER BY {sort_col} {sort_dir}"

    cursor.execute(query, params)
    data = cursor.fetchall()

    if search:
        data = [c for c in data if search in (c[1] or "").lower()]

    return render_template(
        "candidates.html",
        candidates=data,
        sort=sort,
        direction=direction,
        status_filter=status_filter,
        search=search
    )


# ---------------- Analytics Page ----------------
@app.route("/analytics")
def analytics():

    cursor.execute("SELECT score, status, rating FROM candidates")
    data = cursor.fetchall()

    total = len(data)

    shortlisted = len([c for c in data if c[1] == "Shortlisted"])
    rejected = len([c for c in data if c[1] == "Rejected"])
    review = len([c for c in data if c[1] == "Needs Review"])

    shortlisted_scores = [c[0] for c in data if c[1] == "Shortlisted"]
    review_scores = [c[0] for c in data if c[1] == "Needs Review"]
    rejected_scores = [c[0] for c in data if c[1] == "Rejected"]

    avg_shortlisted = int(sum(shortlisted_scores) / len(shortlisted_scores)) if shortlisted_scores else 0
    avg_review = int(sum(review_scores) / len(review_scores)) if review_scores else 0
    avg_rejected = int(sum(rejected_scores) / len(rejected_scores)) if rejected_scores else 0

    ratings = [c[2] for c in data if c[2] is not None]
    avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else 0

    return render_template(
        "analytics.html",
        total=total,
        shortlisted=shortlisted,
        rejected=rejected,
        review=review,
        avg_shortlisted=avg_shortlisted,
        avg_review=avg_review,
        avg_rejected=avg_rejected,
        avg_rating=avg_rating
    )


# ---------------- Settings Page ----------------
@app.route("/settings")
def settings():
    return render_template("settings.html")


# ---------------- Export CSV ----------------
@app.route("/export")
def export_csv():
    status_filter = request.args.get("status", "").strip()
    query = "SELECT id, skills, matched, score, status, email, rating FROM candidates"
    params = ()
    if status_filter:
        if status_filter.lower() == "review":
            status_filter = "Needs Review"
        query += " WHERE status = ?"
        params = (status_filter,)

    cursor.execute(query, params)
    rows = cursor.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "skills", "matched", "score", "status", "email", "rating"])
    writer.writerows(rows)

    filename = "candidates.csv" if not status_filter else f"candidates_{status_filter.lower().replace(' ', '_')}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ---------------- Update Status ----------------
@app.route("/update-status", methods=["POST"])
def update_status():
    candidate_id = request.form.get("candidate_id")
    new_status = request.form.get("status")

    if not candidate_id or new_status not in {"Shortlisted", "Rejected"}:
        return redirect(request.referrer or "/dashboard")

    cursor.execute("UPDATE candidates SET status = ? WHERE id = ?", (new_status, candidate_id))
    conn.commit()
    return redirect(request.referrer or "/dashboard")


# ---------------- Update Rating ----------------
@app.route("/update-rating", methods=["POST"])
def update_rating():
    candidate_id = request.form.get("candidate_id")
    rating = request.form.get("rating")

    try:
        rating_val = int(rating)
    except (TypeError, ValueError):
        return redirect(request.referrer or "/dashboard")

    if rating_val < 1 or rating_val > 5:
        return redirect(request.referrer or "/dashboard")

    cursor.execute("UPDATE candidates SET rating = ? WHERE id = ?", (rating_val, candidate_id))
    conn.commit()
    return redirect(request.referrer or "/dashboard")


# ---------------- Download Resume ----------------
@app.route("/download/<int:candidate_id>")
def download(candidate_id):
    cursor.execute("SELECT status, resume_path FROM candidates WHERE id = ?", (candidate_id,))
    row = cursor.fetchone()
    if not row:
        abort(404)

    status, rel_path = row
    if status != "Shortlisted":
        abort(403)

    if not rel_path:
        abort(404)

    base_dir = os.path.abspath(app.config["UPLOAD_FOLDER"])
    abs_path = os.path.abspath(os.path.join(base_dir, rel_path))
    if not abs_path.startswith(base_dir):
        abort(403)

    if not os.path.exists(abs_path):
        abort(404)

    return send_file(abs_path, as_attachment=True, download_name=os.path.basename(abs_path))


# ---------------- Candidate Detail ----------------
@app.route("/candidate/<int:candidate_id>")
def candidate_detail(candidate_id):
    cursor.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,))
    c = cursor.fetchone()
    if not c:
        abort(404)
    return render_template("candidate_detail.html", c=c)


# ---------------- Resume Preview ----------------
@app.route("/preview/<int:candidate_id>")
def preview(candidate_id):
    cursor.execute("SELECT resume_path FROM candidates WHERE id = ?", (candidate_id,))
    row = cursor.fetchone()
    if not row or not row[0]:
        abort(404)

    base_dir = os.path.abspath(app.config["UPLOAD_FOLDER"])
    abs_path = os.path.abspath(os.path.join(base_dir, row[0]))
    if not abs_path.startswith(base_dir):
        abort(403)

    if not os.path.exists(abs_path):
        abort(404)

    return send_file(abs_path, mimetype="application/pdf", as_attachment=False)


# ---------------- Run Flask ----------------
if __name__ == "__main__":
    print("Starting TalentScan AI server...")
    app.run(debug=True)
