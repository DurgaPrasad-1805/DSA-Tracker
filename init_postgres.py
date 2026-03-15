"""
Run this ONCE after setting up Render PostgreSQL:
  python init_postgres.py

It creates all tables and seeds the data from the existing SQLite database.
"""
import os, sqlite3, psycopg2, json

DATABASE_URL = os.environ["DATABASE_URL"]
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

pg = psycopg2.connect(DATABASE_URL)
cur = pg.cursor()

print("Creating tables...")
cur.execute("""
CREATE TABLE IF NOT EXISTS meta (
    id INTEGER PRIMARY KEY,
    streak INTEGER DEFAULT 0,
    day_number INTEGER DEFAULT 0,
    last_active TEXT DEFAULT '',
    longest_streak INTEGER DEFAULT 0
)""")
cur.execute("""
CREATE TABLE IF NOT EXISTS problems (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE,
    pattern TEXT,
    topic TEXT,
    difficulty TEXT DEFAULT 'Medium',
    status INTEGER DEFAULT 0
)""")
cur.execute("""
CREATE TABLE IF NOT EXISTS subjects (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE,
    status INTEGER DEFAULT 0
)""")
cur.execute("""
CREATE TABLE IF NOT EXISTS roadmap_days (
    day_number INTEGER PRIMARY KEY,
    phase INTEGER,
    phase_name TEXT,
    topic TEXT,
    status INTEGER DEFAULT 0
)""")
cur.execute("""
CREATE TABLE IF NOT EXISTS daily_progress (
    date TEXT PRIMARY KEY,
    count INTEGER DEFAULT 0
)""")
cur.execute("""
CREATE TABLE IF NOT EXISTS video_watched (
    video_key TEXT PRIMARY KEY,
    watched INTEGER DEFAULT 0
)""")
pg.commit()

# Seed from problems.json
print("Seeding problems...")
with open("data/problems.json") as f:
    problems = json.load(f)
for p in problems:
    cur.execute("""
        INSERT INTO problems(name, pattern, topic, difficulty, status)
        VALUES(%s, %s, %s, %s, 0)
        ON CONFLICT(name) DO NOTHING
    """, (p["name"], p.get("pattern",""), p["topic"], p.get("difficulty","Medium")))

# Seed meta
cur.execute("INSERT INTO meta(id, streak, day_number, last_active, longest_streak) VALUES(1,0,0,'',0) ON CONFLICT(id) DO NOTHING")

# Seed subjects
for s in ["DSA","DBMS","Operating Systems","Computer Networks","OOPs","Machine Learning"]:
    cur.execute("INSERT INTO subjects(name, status) VALUES(%s, 0) ON CONFLICT(name) DO NOTHING", (s,))

# Seed roadmap_days
roadmap = [
    *[(d, 1, "Foundations",         "Algorithmic Thinking + Complexity") for d in range(1,4)],
    *[(d, 1, "Foundations",         "Arrays")                            for d in range(4,8)],
    *[(d, 1, "Foundations",         "Binary Search")                     for d in range(8,11)],
    *[(d, 1, "Foundations",         "Strings")                           for d in range(11,15)],
    *[(d, 1, "Foundations",         "Linked List")                       for d in range(15,21)],
    *[(d, 2, "Core Structures",     "Stack")                             for d in range(21,26)],
    *[(d, 2, "Core Structures",     "Queue")                             for d in range(26,31)],
    *[(d, 2, "Core Structures",     "Hash Tables")                       for d in range(31,36)],
    *[(d, 3, "Important Patterns",  "Recursion")                         for d in range(36,41)],
    *[(d, 3, "Important Patterns",  "Backtracking")                      for d in range(41,46)],
    *[(d, 3, "Important Patterns",  "Sorting Algorithms")                for d in range(46,51)],
    *[(d, 3, "Important Patterns",  "Heap / Priority Queue")             for d in range(51,56)],
    *[(d, 4, "Trees + Graphs",      "Trees")                             for d in range(56,66)],
    *[(d, 4, "Trees + Graphs",      "Trie")                              for d in range(66,71)],
    *[(d, 4, "Trees + Graphs",      "Graph Basics")                      for d in range(71,76)],
    *[(d, 5, "Advanced Algorithms", "Graph Algorithms")                  for d in range(76,81)],
    *[(d, 5, "Advanced Algorithms", "Dynamic Programming")               for d in range(81,87)],
    *[(d, 5, "Advanced Algorithms", "Mock Interviews + Revision")        for d in range(87,91)],
]
for day_num, phase, phase_name, topic in roadmap:
    cur.execute("""
        INSERT INTO roadmap_days(day_number, phase, phase_name, topic, status)
        VALUES(%s, %s, %s, %s, 0)
        ON CONFLICT(day_number) DO NOTHING
    """, (day_num, phase, phase_name, topic))

pg.commit()
pg.close()
print("✅ PostgreSQL seeded successfully!")