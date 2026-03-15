from flask import Flask, render_template, request, redirect, session
from datetime import datetime, timedelta
import PyPDF2
import requests

app = Flask(__name__)
app.secret_key = "supersecretkey"

OPENROUTER_API_KEY = "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"

doses = []

# ---------------- CHECK MISSED DOSES ----------------
def check_missed():
    now = datetime.now()

    for dose in doses:

        today_day = now.strftime("%A")

        if today_day not in dose["days"]:
            continue

        dose_datetime = datetime.strptime(
            dose["date"] + " " + dose["time"],
            "%Y-%m-%d %H:%M"
        )

        if dose["status"] == "Pending" and now > dose_datetime:
            dose["status"] = "Missed"


# ---------------- LOGIN ----------------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        session["user"] = request.form["username"]
        return redirect("/dashboard")
    return render_template("login.html")


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")

    check_missed()

    missed = sum(1 for d in doses if d["status"] == "Missed")
    taken = sum(1 for d in doses if d["status"] == "Taken")

    total = missed + taken
    adherence = round((taken / total) * 100, 2) if total > 0 else 0

    if missed == 0:
        risk = "Low"
    elif missed == 1:
        risk = "Medium"
    else:
        risk = "High"

    return render_template(
        "dashboard.html",
        doses=doses,
        adherence=adherence,
        missed=missed,
        risk=risk
    )


# ---------------- ADD DOSE ----------------
@app.route("/add", methods=["POST"])
def add_dose():

    today = datetime.now().strftime("%Y-%m-%d")

    selected_days = request.form.getlist("days")

    if "Everyday" in selected_days:
        selected_days = [
            "Monday","Tuesday","Wednesday",
            "Thursday","Friday","Saturday","Sunday"
        ]

    if not selected_days:
        selected_days = [datetime.now().strftime("%A")]

    doses.append({
        "id": len(doses),
        "name": request.form["name"],
        "time": request.form["time"],
        "date": today,
        "days": selected_days,
        "status": "Pending"
    })

    return redirect("/dashboard")


# ---------------- FIND NEXT DAY ----------------
def next_selected_day(current_date, selected_days):

    for i in range(1,8):
        next_day = current_date + timedelta(days=i)
        if next_day.strftime("%A") in selected_days:
            return next_day


# ---------------- MARK AS TAKEN ----------------
@app.route("/taken/<int:id>")
def mark_taken(id):

    doses[id]["status"] = "Taken"

    current_date = datetime.strptime(doses[id]["date"], "%Y-%m-%d")

    next_day = next_selected_day(current_date, doses[id]["days"])

    doses.append({
        "id": len(doses),
        "name": doses[id]["name"],
        "time": doses[id]["time"],
        "date": next_day.strftime("%Y-%m-%d"),
        "days": doses[id]["days"],
        "status": "Pending"
    })

    return redirect("/dashboard")


# ---------------- AI REPORT ANALYSIS ----------------
@app.route("/upload", methods=["POST"])
def upload_report():

    file = request.files["report"]

    if not file.filename.endswith(".pdf"):
        return "Please upload a valid PDF file."

    reader = PyPDF2.PdfReader(file)
    text = ""

    for page in reader.pages:
        if page.extract_text():
            text += page.extract_text()

    prompt = f"""
Analyze this medical report and give summary and health advice.

{text}
"""

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "meta-llama/llama-3-8b-instruct",
            "messages": [
                {"role": "system", "content": "You are a medical AI assistant."},
                {"role": "user", "content": prompt}
            ]
        }
    )

    result = response.json()
    result_text = result["choices"][0]["message"]["content"]

    return render_template("ai_result.html", result=result_text)


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)