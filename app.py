from flask import Flask, render_template, jsonify, request
import sqlite3
from datetime import datetime, date, timedelta

app = Flask(__name__)

# ── Start date & day rollover time ───────────────────────────────────────────
# Day 1 = March 9, 2026
# A new "study day" begins at 05:30 AM (not midnight)
# So if it's 2:00 AM on March 10, it's still considered Day 1 (previous study day)

START_DATE   = date(2026, 3, 9)
ROLLOVER_HOUR   = 5
ROLLOVER_MINUTE = 30

def get_study_date():
    """
    Returns the current 'study date'.
    Before 5:30 AM, it belongs to the previous study day.
    e.g. 3:00 AM on Mar 10 → study date is still Mar 9
    """
    now = datetime.now()
    rollover = now.replace(hour=ROLLOVER_HOUR, minute=ROLLOVER_MINUTE, second=0, microsecond=0)
    if now < rollover:
        return (now - timedelta(days=1)).date()
    return now.date()

def get_current_day():
    """Returns day number (1–90) based on study date from START_DATE."""
    study_date = get_study_date()
    delta = (study_date - START_DATE).days + 1
    return max(1, min(delta, 90))

def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

def sync_day(conn):
    """Sync day_number in meta table with current calculated day."""
    day = get_current_day()
    conn.execute("UPDATE meta SET day_number=? WHERE id=1", (day,))
    return day

def get_days_until_start():
    """Returns how many days until prep starts. 0 or negative means started."""
    return (START_DATE - get_study_date()).days

# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def home():
    conn   = get_db()
    solved = conn.execute("SELECT COUNT(*) FROM problems WHERE status=1").fetchone()[0]
    total  = conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0]
    streak = conn.execute("SELECT streak FROM meta WHERE id=1").fetchone()

    study_date = get_study_date()
    days_until_start = (START_DATE - study_date).days

    if days_until_start > 0:
        # Prep hasn't started yet
        conn.close()
        return render_template("index.html",
            solved=solved, total=total,
            streak=0,
            day=0,
            days_until_start=days_until_start,
            started=False)
    else:
        day = sync_day(conn)
        conn.commit()
        conn.close()
        return render_template("index.html",
            solved=solved, total=total,
            streak=streak[0] if streak else 0,
            day=day,
            days_until_start=0,
            started=True)

@app.route("/dsa")
def dsa():
    conn = get_db()
    sync_day(conn); conn.commit()
    problems = conn.execute("SELECT * FROM problems ORDER BY topic, id").fetchall()
    conn.close()
    return render_template("dsa.html", problems=problems)

@app.route("/subjects")
def subjects():
    conn = get_db()
    sync_day(conn); conn.commit()
    subjects = conn.execute("SELECT * FROM subjects").fetchall()
    conn.close()
    return render_template("subjects.html", subjects=subjects)

@app.route("/timetable")
def timetable():
    return render_template("timetable.html")

@app.route("/roadmap")
def roadmap():
    conn = get_db()
    sync_day(conn); conn.commit()
    days = conn.execute("SELECT * FROM roadmap_days ORDER BY day_number").fetchall()
    conn.close()
    return render_template("roadmap.html", days=days)

# ── API ──────────────────────────────────────────────────────────────────────

@app.route("/api/toggle_problem/<int:pid>", methods=["POST"])
def toggle_problem(pid):
    conn = get_db()
    cur  = conn.execute("SELECT status FROM problems WHERE id=?", (pid,)).fetchone()
    if cur:
        new_status = 1 - cur[0]
        conn.execute("UPDATE problems SET status=? WHERE id=?", (new_status, pid))
        # Streak: use study_date (not raw date) so after-midnight work counts for today
        study_today = get_study_date().isoformat()
        meta = conn.execute("SELECT last_active, streak FROM meta WHERE id=1").fetchone()
        if meta and meta["last_active"] != study_today and new_status == 1:
            conn.execute("UPDATE meta SET last_active=?, streak=streak+1 WHERE id=1", (study_today,))
        conn.commit()
        solved = conn.execute("SELECT COUNT(*) FROM problems WHERE status=1").fetchone()[0]
        conn.close()
        return jsonify({"ok": True, "status": new_status, "solved": solved})
    conn.close()
    return jsonify({"ok": False}), 404

@app.route("/api/toggle_subject/<int:sid>", methods=["POST"])
def toggle_subject(sid):
    conn = get_db()
    cur  = conn.execute("SELECT status FROM subjects WHERE id=?", (sid,)).fetchone()
    if cur:
        new_status = 1 - cur[0]
        conn.execute("UPDATE subjects SET status=? WHERE id=?", (new_status, sid))
        conn.commit()
        conn.close()
        return jsonify({"ok": True, "status": new_status})
    conn.close()
    return jsonify({"ok": False}), 404

@app.route("/api/toggle_day/<int:day_num>", methods=["POST"])
def toggle_day(day_num):
    conn  = get_db()
    cur   = conn.execute("SELECT status FROM roadmap_days WHERE day_number=?", (day_num,)).fetchone()
    if cur:
        new_status = 1 - cur[0]
        conn.execute("UPDATE roadmap_days SET status=? WHERE day_number=?", (new_status, day_num))
        conn.commit()
        phase = conn.execute("SELECT phase FROM roadmap_days WHERE day_number=?", (day_num,)).fetchone()[0]
        done  = conn.execute("SELECT COUNT(*) FROM roadmap_days WHERE phase=? AND status=1", (phase,)).fetchone()[0]
        total = conn.execute("SELECT COUNT(*) FROM roadmap_days WHERE phase=?", (phase,)).fetchone()[0]
        conn.close()
        return jsonify({"ok": True, "status": new_status, "phase_done": done, "phase_total": total})
    conn.close()
    return jsonify({"ok": False}), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)