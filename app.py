from flask import Flask, render_template, jsonify, request
import os
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

app = Flask(__name__)

START_DATE      = date(2026, 3, 8)
ROLLOVER_HOUR   = 5
ROLLOVER_MINUTE = 30

# ── Database: PostgreSQL on Render, SQLite locally ────────────────────────────
DATABASE_URL = os.environ.get("DATABASE_URL")  # Set this on Render

if DATABASE_URL:
    # Render provides postgres://... but psycopg2 needs postgresql://
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    import psycopg2
    import psycopg2.extras
    DB_TYPE = "postgres"
else:
    import sqlite3
    DB_TYPE = "sqlite"
    DB_PATH = "database.db"

def get_db():
    if DB_TYPE == "postgres":
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        return conn
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        _run_migrations_sqlite(conn)
        return conn

def _run_migrations_sqlite(conn):
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

def _run_migrations_postgres(conn):
    cur = conn.cursor()
    stmts = [
        "ALTER TABLE meta ADD COLUMN IF NOT EXISTS longest_streak INTEGER DEFAULT 0",
        """CREATE TABLE IF NOT EXISTS daily_progress (
            date  TEXT PRIMARY KEY,
            count INTEGER DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS video_watched (
            video_key TEXT PRIMARY KEY,
            watched   INTEGER DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS meta (
            id INTEGER PRIMARY KEY,
            streak INTEGER DEFAULT 0,
            day_number INTEGER DEFAULT 0,
            last_active TEXT DEFAULT '',
            longest_streak INTEGER DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS problems (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE,
            pattern TEXT,
            topic TEXT,
            difficulty TEXT DEFAULT 'Medium',
            status INTEGER DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS subjects (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE,
            status INTEGER DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS roadmap_days (
            day_number INTEGER PRIMARY KEY,
            phase INTEGER,
            phase_name TEXT,
            topic TEXT,
            status INTEGER DEFAULT 0
        )""",
    ]
    for sql in stmts:
        try:
            cur.execute(sql)
        except Exception:
            conn.rollback()
            cur = conn.cursor()
    conn.commit()

def query(conn, sql, params=(), one=False):
    """Unified query helper for both SQLite and PostgreSQL."""
    if DB_TYPE == "postgres":
        sql = sql.replace("?", "%s")
        sql = sql.replace("INTEGER DEFAULT 0", "INTEGER DEFAULT 0")
    cur = conn.cursor()
    cur.execute(sql, params)
    if one:
        row = cur.fetchone()
        if row is None:
            return None
        if DB_TYPE == "postgres":
            return row  # already a dict
        return row
    rows = cur.fetchall()
    return rows

def execute(conn, sql, params=()):
    if DB_TYPE == "postgres":
        sql = sql.replace("?", "%s")
    cur = conn.cursor()
    cur.execute(sql, params)

def get_study_date():
    now = datetime.now(IST)
    rollover = now.replace(hour=ROLLOVER_HOUR, minute=ROLLOVER_MINUTE, second=0, microsecond=0)
    if now < rollover:
        return (now - timedelta(days=1)).date()
    return now.date()

def get_current_day():
    study_date = get_study_date()
    delta = (study_date - START_DATE).days + 1
    return max(1, min(delta, 90))

def row_val(row, key, default=0):
    """Get value from either sqlite Row or psycopg2 RealDictRow."""
    try:
        return row[key]
    except (KeyError, TypeError, IndexError):
        return default

def sync_day(conn):
    day = get_current_day()
    execute(conn, "UPDATE meta SET day_number=? WHERE id=1", (day,))
    return day

# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def home():
    try:
        conn        = get_db()
        if DB_TYPE == "postgres":
            _run_migrations_postgres(conn)

        solved      = query(conn, "SELECT COUNT(*) as c FROM problems WHERE status=1", one=True)
        solved      = row_val(solved, "c", 0) if solved else 0
        total       = query(conn, "SELECT COUNT(*) as c FROM problems", one=True)
        total       = row_val(total, "c", 0) if total else 0
        vid_watched = query(conn, "SELECT COUNT(*) as c FROM video_watched WHERE watched=1", one=True)
        vid_watched = row_val(vid_watched, "c", 0) if vid_watched else 0
        meta        = query(conn, "SELECT streak, longest_streak FROM meta WHERE id=1", one=True)

        study_date       = get_study_date()
        days_until_start = (START_DATE - study_date).days
        streak           = row_val(meta, "streak", 0)
        longest_streak   = row_val(meta, "longest_streak", 0)

        if days_until_start > 0:
            conn.close()
            return render_template("index.html",
                solved=solved, total=total, vid_watched=vid_watched,
                streak=0, longest_streak=0,
                day=0, days_until_start=days_until_start, started=False, current_day=0)
        else:
            day = sync_day(conn)
            conn.commit()
            conn.close()
            return render_template("index.html",
                solved=solved, total=total, vid_watched=vid_watched,
                streak=streak, longest_streak=longest_streak,
                day=day, days_until_start=0, started=True, current_day=day)
    except Exception as e:
        import traceback
        return f"<h2>Error in home route</h2><pre>{traceback.format_exc()}</pre>", 500

@app.route("/dsa")
def dsa():
    conn = get_db()
    sync_day(conn); conn.commit()
    problems = query(conn, "SELECT * FROM problems ORDER BY topic, id")
    conn.close()
    return render_template("dsa.html", problems=problems)

@app.route("/subjects")
def subjects():
    conn = get_db()
    sync_day(conn); conn.commit()
    subs = query(conn, "SELECT * FROM subjects")
    conn.close()
    return render_template("subjects.html", subjects=subs)

@app.route("/timetable")
def timetable():
    return render_template("timetable.html")

@app.route("/roadmap")
def roadmap():
    conn = get_db()
    day = sync_day(conn); conn.commit()
    days = query(conn, "SELECT * FROM roadmap_days ORDER BY day_number")
    conn.close()
    return render_template("roadmap.html", days=days, current_day=day)

# ── API ──────────────────────────────────────────────────────────────────────

@app.route("/api/toggle_problem/<int:pid>", methods=["POST"])
def toggle_problem(pid):
    conn = get_db()
    cur  = query(conn, "SELECT status FROM problems WHERE id=?", (pid,), one=True)
    if cur:
        new_status = 1 - row_val(cur, "status", 0)
        execute(conn, "UPDATE problems SET status=? WHERE id=?", (new_status, pid))

        study_today = get_study_date().isoformat()

        if new_status == 1:
            if DB_TYPE == "postgres":
                execute(conn, """
                    INSERT INTO daily_progress(date, count) VALUES(%s,1)
                    ON CONFLICT(date) DO UPDATE SET count=daily_progress.count+1
                """.replace("?","%s"), (study_today,))
            else:
                execute(conn, """
                    INSERT INTO daily_progress(date, count) VALUES(?,1)
                    ON CONFLICT(date) DO UPDATE SET count=count+1
                """, (study_today,))
            meta = query(conn, "SELECT last_active, streak, longest_streak FROM meta WHERE id=1", one=True)
            if meta and row_val(meta, "last_active", "") != study_today:
                yesterday   = (get_study_date() - timedelta(days=1)).isoformat()
                cur_streak  = row_val(meta, "streak", 0)
                last_active = row_val(meta, "last_active", "")
                new_streak  = (cur_streak + 1) if last_active == yesterday else 1
                new_longest = max(new_streak, row_val(meta, "longest_streak", 0) or 0)
                execute(conn,
                    "UPDATE meta SET last_active=?, streak=?, longest_streak=? WHERE id=1",
                    (study_today, new_streak, new_longest)
                )
        else:
            execute(conn, "UPDATE daily_progress SET count=MAX(0,count-1) WHERE date=?", (study_today,))

        conn.commit()
        solved_row = query(conn, "SELECT COUNT(*) as c FROM problems WHERE status=1", one=True)
        solved = row_val(solved_row, "c", 0)
        meta   = query(conn, "SELECT streak, longest_streak FROM meta WHERE id=1", one=True)
        conn.close()
        return jsonify({
            "ok": True, "status": new_status, "solved": solved,
            "streak": row_val(meta, "streak", 0),
            "longest_streak": row_val(meta, "longest_streak", 0)
        })
    conn.close()
    return jsonify({"ok": False}), 404

@app.route("/api/toggle_subject/<int:sid>", methods=["POST"])
def toggle_subject(sid):
    conn = get_db()
    cur  = query(conn, "SELECT status FROM subjects WHERE id=?", (sid,), one=True)
    if cur:
        new_status = 1 - row_val(cur, "status", 0)
        execute(conn, "UPDATE subjects SET status=? WHERE id=?", (new_status, sid))
        conn.commit()
        conn.close()
        return jsonify({"ok": True, "status": new_status})
    conn.close()
    return jsonify({"ok": False}), 404

@app.route("/api/toggle_day/<int:day_num>", methods=["POST"])
def toggle_day(day_num):
    current_day = get_current_day()
    conn  = get_db()
    cur   = query(conn, "SELECT status FROM roadmap_days WHERE day_number=?", (day_num,), one=True)
    if cur:
        current_status = row_val(cur, "status", 0)

        # Block future days
        if day_num > current_day:
            conn.close()
            return jsonify({"ok": False, "reason": "future"}), 403

        # Block past days (both done and missed — immutable)
        if day_num < current_day:
            conn.close()
            return jsonify({"ok": False, "reason": "past_locked"}), 403

        # Only today can toggle
        new_status = 1 - current_status
        execute(conn, "UPDATE roadmap_days SET status=? WHERE day_number=?", (new_status, day_num))
        conn.commit()
        phase_row = query(conn, "SELECT phase FROM roadmap_days WHERE day_number=?", (day_num,), one=True)
        phase = row_val(phase_row, "phase", 1)
        done_row  = query(conn, "SELECT COUNT(*) as c FROM roadmap_days WHERE phase=? AND status=1", (phase,), one=True)
        total_row = query(conn, "SELECT COUNT(*) as c FROM roadmap_days WHERE phase=?", (phase,), one=True)
        conn.close()
        return jsonify({
            "ok": True, "status": new_status,
            "phase_done": row_val(done_row, "c", 0),
            "phase_total": row_val(total_row, "c", 0)
        })
    conn.close()
    return jsonify({"ok": False}), 404

@app.route("/api/toggle_video", methods=["POST"])
def toggle_video():
    data    = request.get_json()
    vkey    = data.get("vkey","")
    conn    = get_db()
    row     = query(conn, "SELECT watched FROM video_watched WHERE video_key=?", (vkey,), one=True)
    if row:
        new_val = 0 if row_val(row, "watched", 0) else 1
        execute(conn, "UPDATE video_watched SET watched=? WHERE video_key=?", (new_val, vkey))
    else:
        new_val = 1
        execute(conn, "INSERT INTO video_watched(video_key, watched) VALUES(?,1)", (vkey,))
    conn.commit()
    conn.close()
    return jsonify(ok=True, watched=new_val)

@app.route("/api/video_watched_all")
def video_watched_all():
    conn = get_db()
    rows = query(conn, "SELECT video_key FROM video_watched WHERE watched=1")
    conn.close()
    return jsonify(watched=[row_val(r, "video_key", "") for r in rows])

@app.route("/api/weekly_progress")
def weekly_progress():
    conn = get_db()
    rows = query(conn, "SELECT date, count FROM daily_progress ORDER BY date")
    conn.close()
    weekly = {}
    for row in rows:
        d = date.fromisoformat(row_val(row, "date", ""))
        delta = (d - START_DATE).days
        if delta < 0:
            continue
        week_num = delta // 7 + 1
        if week_num > 13:
            continue
        label = f"W{week_num}"
        weekly[label] = weekly.get(label, 0) + row_val(row, "count", 0)
    all_weeks = [f"W{i}" for i in range(1, 14)]
    return jsonify([{"week": w, "count": weekly.get(w, 0)} for w in all_weeks])

@app.route("/api/daily_counts")
def daily_counts():
    conn = get_db()
    rows = query(conn, "SELECT date, count FROM daily_progress")
    conn.close()
    return jsonify({row_val(r, "date", ""): row_val(r, "count", 0) for r in rows})

@app.route("/api/current_day")
def api_current_day():
    return jsonify({"day": get_current_day()})

def auto_seed():
    """Auto-seed the database on first run if empty."""
    import json
    try:
        conn = get_db()
        if DB_TYPE == "postgres":
            _run_migrations_postgres(conn)
        
        # Check if already seeded
        count = query(conn, "SELECT COUNT(*) as c FROM problems", one=True)
        if count and row_val(count, "c", 0) > 0:
            conn.close()
            return  # Already seeded

        print("Auto-seeding database...")

        # Seed problems from JSON
        with open("data/problems.json") as f:
            problems = json.load(f)
        for p in problems:
            try:
                execute(conn, "INSERT INTO problems(name, pattern, topic, difficulty, status) VALUES(?,?,?,?,0)",
                    (p["name"], p.get("pattern",""), p["topic"], p.get("difficulty","Medium")))
            except: pass

        # Seed meta
        try:
            execute(conn, "INSERT INTO meta(id, streak, day_number, last_active, longest_streak) VALUES(?,0,0,'',0)", (1,))
        except: pass

        # Seed subjects
        for s in ["DSA","DBMS","Operating Systems","Computer Networks","OOPs","Machine Learning"]:
            try:
                execute(conn, "INSERT INTO subjects(name, status) VALUES(?,0)", (s,))
            except: pass

        # Seed roadmap days
        roadmap = [
            *[(d,1,"Foundations","Algorithmic Thinking + Complexity") for d in range(1,4)],
            *[(d,1,"Foundations","Arrays") for d in range(4,8)],
            *[(d,1,"Foundations","Binary Search") for d in range(8,11)],
            *[(d,1,"Foundations","Strings") for d in range(11,15)],
            *[(d,1,"Foundations","Linked List") for d in range(15,21)],
            *[(d,2,"Core Structures","Stack") for d in range(21,26)],
            *[(d,2,"Core Structures","Queue") for d in range(26,31)],
            *[(d,2,"Core Structures","Hash Tables") for d in range(31,36)],
            *[(d,3,"Important Patterns","Recursion") for d in range(36,41)],
            *[(d,3,"Important Patterns","Backtracking") for d in range(41,46)],
            *[(d,3,"Important Patterns","Sorting Algorithms") for d in range(46,51)],
            *[(d,3,"Important Patterns","Heap / Priority Queue") for d in range(51,56)],
            *[(d,4,"Trees + Graphs","Trees") for d in range(56,66)],
            *[(d,4,"Trees + Graphs","Trie") for d in range(66,71)],
            *[(d,4,"Trees + Graphs","Graph Basics") for d in range(71,76)],
            *[(d,5,"Advanced Algorithms","Graph Algorithms") for d in range(76,81)],
            *[(d,5,"Advanced Algorithms","Dynamic Programming") for d in range(81,87)],
            *[(d,5,"Advanced Algorithms","Mock Interviews + Revision") for d in range(87,91)],
        ]
        for day_num, phase, phase_name, topic in roadmap:
            try:
                execute(conn, "INSERT INTO roadmap_days(day_number, phase, phase_name, topic, status) VALUES(?,?,?,?,0)",
                    (day_num, phase, phase_name, topic))
            except: pass

        conn.commit()
        conn.close()
        print("✅ Database seeded successfully!")
    except Exception as e:
        print(f"Seed error: {e}")

auto_seed()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)