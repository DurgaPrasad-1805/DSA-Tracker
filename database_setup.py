import sqlite3, json, os

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DB_PATH   = os.path.join(BASE_DIR, "database.db")
JSON_PATH = os.path.join(BASE_DIR, "data", "problems.json")

conn   = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# ── Tables ────────────────────────────────────────────────────────
cursor.execute("""
CREATE TABLE IF NOT EXISTS problems (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT UNIQUE,
    pattern    TEXT,
    topic      TEXT,
    difficulty TEXT DEFAULT 'Medium',
    status     INTEGER DEFAULT 0
)""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS subjects (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name   TEXT UNIQUE,
    status INTEGER DEFAULT 0
)""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS meta (
    id          INTEGER PRIMARY KEY,
    streak      INTEGER DEFAULT 0,
    day_number  INTEGER DEFAULT 0,
    last_active TEXT DEFAULT ''
)""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS daily_progress (
    date  TEXT PRIMARY KEY,
    count INTEGER DEFAULT 0
)""")

cursor.execute("""
ALTER TABLE meta ADD COLUMN longest_streak INTEGER DEFAULT 0
""") if "longest_streak" not in [r[1] for r in cursor.execute("PRAGMA table_info(meta)").fetchall()] else None

cursor.execute("""
CREATE TABLE IF NOT EXISTS roadmap_days (
    day_number INTEGER PRIMARY KEY,
    phase      INTEGER,
    phase_name TEXT,
    topic      TEXT,
    status     INTEGER DEFAULT 0
)""")

# ── WIPE problems table and reseed cleanly from JSON ─────────────
print("Wiping old problems table...")
# Preserve solved status before wipe
solved_names = set(
    r[0] for r in cursor.execute(
        "SELECT name FROM problems WHERE status=1"
    ).fetchall()
)
print(f"  Preserving {len(solved_names)} solved problems")

cursor.execute("DELETE FROM problems")
cursor.execute("DELETE FROM sqlite_sequence WHERE name='problems'")

with open(JSON_PATH) as f:
    problems = json.load(f)

for p in problems:
    status = 1 if p["name"] in solved_names else 0
    cursor.execute("""
        INSERT INTO problems(name, pattern, topic, difficulty, status)
        VALUES(?, ?, ?, ?, ?)
    """, (p["name"], p["pattern"], p["topic"], p.get("difficulty","Medium"), status))

print(f"  Inserted {len(problems)} problems cleanly")

# ── Meta ──────────────────────────────────────────────────────────
cursor.execute("INSERT OR IGNORE INTO meta(id,streak,day_number,last_active) VALUES(1,0,0,'')")

# ── Subjects — wipe duplicates and reseed ────────────────────────
# Preserve existing done status before cleanup
subject_status = {
    r[0]: r[1] for r in cursor.execute("SELECT name, status FROM subjects").fetchall()
}
cursor.execute("DELETE FROM subjects")
cursor.execute("DELETE FROM sqlite_sequence WHERE name='subjects'")
for s in ["DSA","DBMS","Operating Systems","Computer Networks","OOPs","Machine Learning"]:
    status = subject_status.get(s, 0)
    cursor.execute("INSERT INTO subjects(name, status) VALUES(?,?)", (s, status))
print(f"  Seeded 6 subjects cleanly")

# ── Roadmap Days ──────────────────────────────────────────────────
roadmap = [
    *[(d, 1, "Foundations",          "Algorithmic Thinking + Complexity") for d in range(1,4)],
    *[(d, 1, "Foundations",          "Arrays")                            for d in range(4,8)],
    *[(d, 1, "Foundations",          "Binary Search")                     for d in range(8,11)],
    *[(d, 1, "Foundations",          "Strings")                           for d in range(11,15)],
    *[(d, 1, "Foundations",          "Linked List")                       for d in range(15,21)],
    *[(d, 2, "Core Structures",      "Stack")                             for d in range(21,26)],
    *[(d, 2, "Core Structures",      "Queue")                             for d in range(26,31)],
    *[(d, 2, "Core Structures",      "Hash Tables")                       for d in range(31,36)],
    *[(d, 3, "Important Patterns",   "Recursion")                         for d in range(36,41)],
    *[(d, 3, "Important Patterns",   "Backtracking")                      for d in range(41,46)],
    *[(d, 3, "Important Patterns",   "Sorting Algorithms")                for d in range(46,51)],
    *[(d, 3, "Important Patterns",   "Heap / Priority Queue")             for d in range(51,56)],
    *[(d, 4, "Trees + Graphs",       "Trees")                             for d in range(56,66)],
    *[(d, 4, "Trees + Graphs",       "Trie")                              for d in range(66,71)],
    *[(d, 4, "Trees + Graphs",       "Graph Basics")                      for d in range(71,76)],
    *[(d, 5, "Advanced Algorithms",  "Graph Algorithms")                  for d in range(76,81)],
    *[(d, 5, "Advanced Algorithms",  "Dynamic Programming")               for d in range(81,87)],
    *[(d, 5, "Advanced Algorithms",  "Mock Interviews + Revision")        for d in range(87,91)],
]

for day_num, phase, phase_name, topic in roadmap:
    cursor.execute("""
        INSERT OR IGNORE INTO roadmap_days(day_number, phase, phase_name, topic)
        VALUES(?, ?, ?, ?)
    """, (day_num, phase, phase_name, topic))

conn.commit()

# ── Summary ───────────────────────────────────────────────────────
print("\n✅ Database seeded cleanly!")
total  = cursor.execute("SELECT COUNT(*) FROM problems").fetchone()[0]
topics = cursor.execute("SELECT topic, COUNT(*) as c FROM problems GROUP BY topic ORDER BY topic").fetchall()
print(f"\n{total} problems across {len(topics)} topics:")
for t in topics:
    print(f"  {t[0]}: {t[1]}")

days = cursor.execute("SELECT COUNT(*) FROM roadmap_days").fetchone()[0]
print(f"\n{days} roadmap days seeded")
conn.close()