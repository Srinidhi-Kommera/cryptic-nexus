from flask import (Flask, render_template, request, redirect,
                   url_for, session, jsonify)
from database import (
    init_db, seed_teams, seed_questions,
    verify_team, verify_admin,
    get_team, get_all_teams, get_all_questions,
    get_questions_for_team, get_clues_for_question,
    get_team_solves, assign_questions, get_assigned_questions,
    submit_answer, get_logs, get_leaderboard,
    get_event_config, start_event, add_extra_time, set_duration,
    get_remaining_seconds, is_event_over,
)
import functools

app = Flask(__name__)
app.secret_key = "cn-super-secret-change-me-2024"

# ─── Decorators ───────────────────────────────────────────────────────────────

def team_required(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if "team_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

def admin_required(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return wrapper

# ─── Team Auth ────────────────────────────────────────────────────────────────

@app.route("/", methods=["GET", "POST"])
def login():
    if session.get("team_id"):
        return redirect(url_for("dashboard"))
    error = None
    if request.method == "POST":
        tid = request.form.get("team_id", "").strip().upper()
        pwd = request.form.get("password", "").strip()
        team = verify_team(tid, pwd)
        if team:
            cfg = get_event_config()
            if not cfg.get("started"):
                error = "The event hasn't started yet. Please wait for the admin to start it."
            else:
                session["team_id"] = tid
                session["team_name"] = team["team_name"]
                return redirect(url_for("dashboard"))
        else:
            error = "Invalid Team ID or Password."
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ─── Team pages ───────────────────────────────────────────────────────────────

@app.route("/dashboard")
@team_required
def dashboard():
    tid = session["team_id"]
    team = get_team(tid)
    remaining = get_remaining_seconds()
    cfg = get_event_config()
    return render_template("dashboard.html",
        team=team,
        remaining=remaining if remaining is not None else 0,
        time_up=is_event_over(),
        event_started=cfg.get("started", 0)
    )

@app.route("/round1")
@team_required
def round1():
    tid = session["team_id"]
    if is_event_over():
        return redirect(url_for("time_up"))
    questions = get_questions_for_team(tid, 1)
    solved = get_team_solves(tid)
    qs_with_clues = []
    for q in questions:
        clues = get_clues_for_question(q["id"])
        safe_clues = [{"clue_text": c["clue_text"]} for c in clues]
        qs_with_clues.append({**q, "clues": safe_clues, "is_solved": q["id"] in solved})
    team = get_team(tid)
    remaining = get_remaining_seconds() or 0
    return render_template("round1.html",
        questions=qs_with_clues, team=team, remaining=remaining
    )

@app.route("/round2")
@team_required
def round2():
    tid = session["team_id"]
    if is_event_over():
        return redirect(url_for("time_up"))
    team = get_team(tid)
    if not team["round2_unlocked"]:
        return redirect(url_for("round1"))
    questions = get_questions_for_team(tid, 2)
    solved = get_team_solves(tid)
    qs_with_clues = []
    for q in questions:
        clues = get_clues_for_question(q["id"])
        safe_clues = [{"clue_text": c["clue_text"]} for c in clues]
        
        # Add steganography image filename for R2Q16..R2Q34
        image_file = None
        qid = q["id"]
        if qid.startswith("R2Q"):
            try:
                num = int(qid[3:])          # "R2Q16" -> 16
                if 16 <= num <= 34:
                    stego_index = num - 15   # 16->1, 17->2, ..., 34->19
                    image_file = f"encoded{stego_index}.png"
            except ValueError:
                pass
        
        qs_with_clues.append({
            **q,
            "clues": safe_clues,
            "is_solved": q["id"] in solved,
            "image_file": image_file
        })
    remaining = get_remaining_seconds() or 0
    return render_template("round2.html",
        questions=qs_with_clues, team=team, remaining=remaining
    )

@app.route("/leaderboard")
def leaderboard():
    return render_template("leaderboard.html", teams=get_leaderboard())

@app.route("/timesup")
def time_up():
    tid = session.get("team_id")
    team = get_team(tid) if tid else None
    return render_template("timesup.html", team=team, lb=get_leaderboard())

# ─── Submission API ───────────────────────────────────────────────────────────

@app.route("/submit", methods=["POST"])
@team_required
def submit():
    tid = session["team_id"]
    qid = request.form.get("question_id", "").strip()
    answer = request.form.get("answer", "").strip()
    
    print(f"DEBUG: Submission - Team: {tid}, Question: {qid}, Answer: {answer}")
    
    if not qid or not answer:
        return jsonify({"status": "missing_fields", "message": "Missing question ID or answer"}), 400
    
    result = submit_answer(tid, qid, answer)
    
    print(f"DEBUG: Result - {result}")
    
    return jsonify({
        "status": result.get("status", "error"),
        "score": result.get("score", 0),
        "round2_unlocked": result.get("round2_unlocked", False),
        "attempt": result.get("attempt", 0),
        "message": result.get("message", "")
    })

# ─── Timer API ────────────────────────────────────────────────────────────────

@app.route("/api/time")
def api_time():
    remaining = get_remaining_seconds()
    cfg = get_event_config()
    return jsonify({
        "remaining": remaining if remaining is not None else 0,
        "started": bool(cfg.get("started")),
        "over": is_event_over(),
    })

@app.route("/api/leaderboard")
def api_leaderboard():
    return jsonify(get_leaderboard())

# ─── Admin Auth ───────────────────────────────────────────────────────────────

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("is_admin"):
        return redirect(url_for("admin_dashboard"))
    error = None
    if request.method == "POST":
        u = request.form.get("username", "").strip()
        p = request.form.get("password", "").strip()
        if verify_admin(u, p):
            session["is_admin"] = True
            session["admin_user"] = u
            return redirect(url_for("admin_dashboard"))
        error = "Invalid credentials."
    return render_template("admin_login.html", error=error)

@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    session.pop("admin_user", None)
    return redirect(url_for("admin_login"))

# ─── Admin Dashboard ──────────────────────────────────────────────────────────

@app.route("/admin")
@admin_required
def admin_dashboard():
    cfg = get_event_config()
    remaining = get_remaining_seconds()
    return render_template("admin_dashboard.html",
        cfg=cfg,
        teams=get_all_teams(),
        remaining=remaining,
        questions=get_all_questions(),
    )

@app.route("/admin/start", methods=["POST"])
@admin_required
def admin_start():
    mins = int(request.form.get("duration_minutes", 60))
    start_event(mins * 60)
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/add_time", methods=["POST"])
@admin_required
def admin_add_time():
    mins = int(request.form.get("extra_minutes", 5))
    add_extra_time(mins)
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/set_duration", methods=["POST"])
@admin_required
def admin_set_duration():
    mins = int(request.form.get("duration_minutes", 60))
    set_duration(mins * 60)
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/assign/<team_id>", methods=["GET", "POST"])
@admin_required
def admin_assign(team_id):
    team = get_team(team_id)
    all_questions = get_all_questions()
    if request.method == "POST":
        selected = request.form.getlist("question_ids")
        assign_questions(team_id, selected)
        return redirect(url_for("admin_dashboard"))
    assigned = get_assigned_questions(team_id)
    return render_template("admin_assign.html",
        team=team,
        all_questions=all_questions,
        assigned=assigned
    )

@app.route("/admin/logs")
@admin_required
def admin_logs():
    team_id = request.args.get("team_id")
    logs = get_logs(team_id)
    teams = get_all_teams()
    return render_template("admin_logs.html",
        logs=logs, teams=teams, selected_team=team_id
    )

@app.route("/admin/answers")
@admin_required
def admin_answers():
    return render_template("admin_answers.html", questions=get_all_questions())

@app.route("/admin/leaderboard")
@admin_required
def admin_leaderboard():
    return render_template("admin_leaderboard.html")

@app.route("/admin/api/status")
@admin_required
def admin_api_status():
    return jsonify({
        "teams": get_leaderboard(),
        "remaining": get_remaining_seconds(),
        "config": dict(get_event_config()),
    })

@app.route("/admin/reset", methods=["POST"])
@admin_required
def admin_reset():
    """Complete reset - DANGER ZONE"""
    import sqlite3
    try:
        conn = sqlite3.connect("cryptic_nexus.db")
        c = conn.cursor()
        c.execute("DELETE FROM submissions")
        c.execute("DELETE FROM solves")
        c.execute("DELETE FROM team_questions")
        c.execute("UPDATE teams SET score = 0, round1_solved = 0, round2_unlocked = 0")
        c.execute("UPDATE event_config SET started = 0, start_time = NULL, duration = 3600, extra_time = 0 WHERE id = 1")
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "Event completely reset"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ─── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    seed_teams()
    seed_questions()
    app.run(host="0.0.0.0", port=5000, debug=True)