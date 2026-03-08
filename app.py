from flask import Flask, render_template, jsonify, request
import sqlite3
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

app = Flask(__name__)

START_DATE      = date(2026, 3, 8)
ROLLOVER_HOUR   = 5
ROLLOVER_MINUTE = 30

def get_study_date():
    now = datetime.now(IST)  # Always use IST
    rollover = now.replace(hour=ROLLOVER_HOUR, minute=ROLLOVER_MINUTE, second=0, microsecond=0)
    if now < rollover:
        return (now - timedelta(days=1)).date()
    return now.date()

def get_current_day():
    study_date = get_study_date()
    delta = (study_date - START_DATE).days + 1
    return max(1, min(delta, 90))

def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row

    # Safe migrations — never crash if columns/tables already exist
    migrations = [
        "ALTER TABLE meta ADD COLUMN longest_streak INTEGER DEFAULT 0",
        """CREATE TABLE IF NOT EXISTS daily_progress (
            date  TEXT PRIMARY KEY,
            count INTEGER DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS video_watched (
            video_key TEXT PRIMARY KEY,
            watched   INTEGER DEFAULT 0
        )""",
    ]
    for sql in migrations:
        try:
            conn.execute(sql)
            conn.commit()
        except Exception:
            pass

    return conn

def sync_day(conn):
    day = get_current_day()
    conn.execute("UPDATE meta SET day_number=? WHERE id=1", (day,))
    return day

# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def home():
    try:
        conn        = get_db()
        solved      = conn.execute("SELECT COUNT(*) FROM problems WHERE status=1").fetchone()[0]
        total       = conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0]
        vid_watched = conn.execute("SELECT COUNT(*) FROM video_watched WHERE watched=1").fetchone()[0]
        meta        = conn.execute("SELECT streak, longest_streak FROM meta WHERE id=1").fetchone()

        study_date       = get_study_date()
        days_until_start = (START_DATE - study_date).days
        streak           = meta["streak"]        if meta else 0
        longest_streak   = meta["longest_streak"] if meta else 0

        if days_until_start > 0:
            conn.close()
            return render_template("index.html",
                solved=solved, total=total, vid_watched=vid_watched,
                streak=0, longest_streak=0,
                day=0, days_until_start=days_until_start, started=False)
        else:
            day = sync_day(conn)
            conn.commit()
            conn.close()
            return render_template("index.html",
                solved=solved, total=total, vid_watched=vid_watched,
                streak=streak, longest_streak=longest_streak,
                day=day, days_until_start=0, started=True)
    except Exception as e:
        return f"<h2>Error in home route</h2><pre>{e}</pre>", 500

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

        study_today = get_study_date().isoformat()

        if new_status == 1:
            conn.execute("""
                INSERT INTO daily_progress(date, count) VALUES(?,1)
                ON CONFLICT(date) DO UPDATE SET count=count+1
            """, (study_today,))
            meta = conn.execute("SELECT last_active, streak, longest_streak FROM meta WHERE id=1").fetchone()
            if meta and meta["last_active"] != study_today:
                yesterday  = (get_study_date() - timedelta(days=1)).isoformat()
                new_streak = (meta["streak"] + 1) if meta["last_active"] == yesterday else 1
                new_longest = max(new_streak, meta["longest_streak"] or 0)
                conn.execute(
                    "UPDATE meta SET last_active=?, streak=?, longest_streak=? WHERE id=1",
                    (study_today, new_streak, new_longest)
                )
        else:
            conn.execute("UPDATE daily_progress SET count=MAX(0,count-1) WHERE date=?", (study_today,))

        conn.commit()
        solved = conn.execute("SELECT COUNT(*) FROM problems WHERE status=1").fetchone()[0]
        meta   = conn.execute("SELECT streak, longest_streak FROM meta WHERE id=1").fetchone()
        conn.close()
        return jsonify({
            "ok": True, "status": new_status, "solved": solved,
            "streak": meta["streak"] if meta else 0,
            "longest_streak": meta["longest_streak"] if meta else 0
        })
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

@app.route("/api/toggle_video", methods=["POST"])
def toggle_video():
    data    = request.get_json()
    vkey    = data.get("vkey","")
    conn    = get_db()
    row     = conn.execute("SELECT watched FROM video_watched WHERE video_key=?", (vkey,)).fetchone()
    if row:
        new_val = 0 if row["watched"] else 1
        conn.execute("UPDATE video_watched SET watched=? WHERE video_key=?", (new_val, vkey))
    else:
        new_val = 1
        conn.execute("INSERT INTO video_watched(video_key, watched) VALUES(?,1)", (vkey,))
    conn.commit()
    conn.close()
    return jsonify(ok=True, watched=new_val)

@app.route("/api/video_watched_all")
def video_watched_all():
    conn = get_db()
    rows = conn.execute("SELECT video_key FROM video_watched WHERE watched=1").fetchall()
    conn.close()
    return jsonify(watched=[r["video_key"] for r in rows])

@app.route("/api/weekly_progress")
def weekly_progress():
    conn = get_db()
    rows = conn.execute("SELECT date, count FROM daily_progress ORDER BY date").fetchall()
    conn.close()
    weekly = {}
    for row in rows:
        d = date.fromisoformat(row["date"])
        delta = (d - START_DATE).days
        if delta < 0:
            continue
        week_num = delta // 7 + 1
        if week_num > 13:
            continue
        label = f"W{week_num}"
        weekly[label] = weekly.get(label, 0) + row["count"]
    all_weeks = [f"W{i}" for i in range(1, 14)]
    return jsonify([{"week": w, "count": weekly.get(w, 0)} for w in all_weeks])

@app.route("/api/daily_counts")
def daily_counts():
    conn = get_db()
    rows = conn.execute("SELECT date, count FROM daily_progress").fetchall()
    conn.close()
    return jsonify({r["date"]: r["count"] for r in rows})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)