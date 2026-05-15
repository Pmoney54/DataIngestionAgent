"""
server.py - Student Agent backend for Render
"""

import os
import csv
import json
import io
import time
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_URL     = "https://api.anthropic.com/v1/messages"
PORT              = int(os.environ.get("PORT", 8000))
MAX_QUESTION_LEN  = 1000

SHEET_ID = "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"

# Fallback hardcoded data in case Google Sheets fetch fails
FALLBACK_STUDENTS = [
    {"student_name": "Alexandra", "gender": "Female", "class_level": "4. Senior",    "home_state": "CA", "major": "English", "extracurricular": "Drama Club"},
    {"student_name": "Andrew",    "gender": "Male",   "class_level": "1. Freshman",  "home_state": "SD", "major": "Math",    "extracurricular": "Lacrosse"},
    {"student_name": "Anna",      "gender": "Female", "class_level": "1. Freshman",  "home_state": "NC", "major": "English", "extracurricular": "Basketball"},
    {"student_name": "Becky",     "gender": "Female", "class_level": "2. Sophomore", "home_state": "SD", "major": "Art",     "extracurricular": "Baseball"},
    {"student_name": "Benjamin",  "gender": "Male",   "class_level": "4. Senior",    "home_state": "WI", "major": "English", "extracurricular": "Basketball"},
    {"student_name": "Carl",      "gender": "Male",   "class_level": "3. Junior",    "home_state": "MD", "major": "Art",     "extracurricular": "Debate"},
    {"student_name": "Carrie",    "gender": "Female", "class_level": "3. Junior",    "home_state": "NE", "major": "English", "extracurricular": "Track & Field"},
    {"student_name": "Dorothy",   "gender": "Female", "class_level": "4. Senior",    "home_state": "MD", "major": "Math",    "extracurricular": "Lacrosse"},
    {"student_name": "Dylan",     "gender": "Male",   "class_level": "1. Freshman",  "home_state": "MA", "major": "Math",    "extracurricular": "Baseball"},
    {"student_name": "Edward",    "gender": "Male",   "class_level": "3. Junior",    "home_state": "FL", "major": "English", "extracurricular": "Drama Club"},
    {"student_name": "Ellen",     "gender": "Female", "class_level": "1. Freshman",  "home_state": "WI", "major": "Physics", "extracurricular": "Drama Club"},
    {"student_name": "Fiona",     "gender": "Female", "class_level": "1. Freshman",  "home_state": "MA", "major": "Art",     "extracurricular": "Debate"},
    {"student_name": "John",      "gender": "Male",   "class_level": "3. Junior",    "home_state": "CA", "major": "Physics", "extracurricular": "Basketball"},
    {"student_name": "Jonathan",  "gender": "Male",   "class_level": "2. Sophomore", "home_state": "SC", "major": "Math",    "extracurricular": "Debate"},
    {"student_name": "Joseph",    "gender": "Male",   "class_level": "1. Freshman",  "home_state": "AK", "major": "English", "extracurricular": "Drama Club"},
    {"student_name": "Josephine", "gender": "Female", "class_level": "1. Freshman",  "home_state": "NY", "major": "Math",    "extracurricular": "Debate"},
    {"student_name": "Karen",     "gender": "Female", "class_level": "2. Sophomore", "home_state": "NH", "major": "English", "extracurricular": "Basketball"},
    {"student_name": "Kevin",     "gender": "Male",   "class_level": "2. Sophomore", "home_state": "NE", "major": "Physics", "extracurricular": "Drama Club"},
    {"student_name": "Lisa",      "gender": "Female", "class_level": "3. Junior",    "home_state": "SC", "major": "Art",     "extracurricular": "Lacrosse"},
    {"student_name": "Mary",      "gender": "Female", "class_level": "2. Sophomore", "home_state": "AK", "major": "Physics", "extracurricular": "Track & Field"},
    {"student_name": "Maureen",   "gender": "Female", "class_level": "1. Freshman",  "home_state": "CA", "major": "Physics", "extracurricular": "Basketball"},
    {"student_name": "Nick",      "gender": "Male",   "class_level": "4. Senior",    "home_state": "NY", "major": "Art",     "extracurricular": "Baseball"},
    {"student_name": "Olivia",    "gender": "Female", "class_level": "4. Senior",    "home_state": "NC", "major": "Physics", "extracurricular": "Track & Field"},
    {"student_name": "Pamela",    "gender": "Female", "class_level": "3. Junior",    "home_state": "RI", "major": "Math",    "extracurricular": "Baseball"},
    {"student_name": "Patrick",   "gender": "Male",   "class_level": "1. Freshman",  "home_state": "NY", "major": "Art",     "extracurricular": "Lacrosse"},
    {"student_name": "Robert",    "gender": "Male",   "class_level": "1. Freshman",  "home_state": "CA", "major": "English", "extracurricular": "Track & Field"},
    {"student_name": "Sean",      "gender": "Male",   "class_level": "1. Freshman",  "home_state": "NH", "major": "Physics", "extracurricular": "Track & Field"},
    {"student_name": "Stacy",     "gender": "Female", "class_level": "1. Freshman",  "home_state": "NY", "major": "Math",    "extracurricular": "Baseball"},
    {"student_name": "Thomas",    "gender": "Male",   "class_level": "2. Sophomore", "home_state": "RI", "major": "Art",     "extracurricular": "Lacrosse"},
    {"student_name": "Will",      "gender": "Male",   "class_level": "4. Senior",    "home_state": "FL", "major": "Math",    "extracurricular": "Debate"},
]

# Fix #1: cache student data so Google Sheets is not hit on every request
_students_cache     = None
_cache_timestamp    = 0.0
_CACHE_TTL          = 300  # seconds


def fetch_students():
    global _students_cache, _cache_timestamp

    now = time.time()
    if _students_cache is not None and (now - _cache_timestamp) < _CACHE_TTL:
        return _students_cache

    urls = [
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Sheet1",
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0",
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/pub?output=csv",
    ]
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                content = r.read().decode("utf-8")
            rows = list(csv.DictReader(io.StringIO(content)))
            students = []
            for row in rows:
                name = row.get("Student Name", "").strip()
                if not name:
                    continue
                students.append({
                    "student_name":    name,
                    "gender":          row.get("Gender", "").strip(),
                    "class_level":     row.get("Class Level", "").strip(),
                    "home_state":      row.get("Home State", "").strip(),
                    "major":           row.get("Major", "").strip(),
                    "extracurricular": row.get("Extracurricular Activity", "").strip(),
                })
            if students:
                print(f"Fetched {len(students)} students from: {url}")
                _students_cache  = students
                _cache_timestamp = now
                return students
        except Exception as e:
            print(f"Failed to fetch from {url}: {e}")

    print("All Google Sheet URLs failed — using fallback hardcoded data.")
    # Don't cache the fallback so the next request retries Sheets
    return FALLBACK_STUDENTS


def ask_claude(question, students, api_key):
    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 1024,
        "system": (
            "You are a data analyst for a student database. "
            "Answer questions accurately using ONLY the provided data. "
            "Be concise. Columns: student_name, gender, class_level "
            "(1. Freshman / 2. Sophomore / 3. Junior / 4. Senior), "
            "home_state, major, extracurricular."
        ),
        "messages": [{"role": "user", "content": f"Question: {question}\n\nData:\n{json.dumps(students)}"}],
    }).encode()

    req = urllib.request.Request(
        ANTHROPIC_URL, data=payload,
        headers={
            "Content-Type":      "application/json",
            "x-api-key":         api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            result = json.loads(r.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        print(f"Anthropic API {e.code} error: {error_body}")
        raise RuntimeError(f"Anthropic API error {e.code}: {error_body}") from e

    # Fix #6: removed dead "completion" branch (old completions API, never returned by Messages API)
    if "content" in result and isinstance(result["content"], list) and result["content"]:
        return result["content"][0].get("text", "")
    return json.dumps(result)


# Fix #2: threaded server so concurrent requests don't block each other
class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class Handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        print(f"{self.address_string()} - {format % args}")

    def send_json(self, status, data):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")  # Fix #7
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            self.send_json(200, {"status": "ok"})
        else:
            self.send_json(404, {"error": "Not found. POST to /ask"})

    def do_POST(self):
        if self.path != "/ask":
            self.send_json(404, {"error": "Not found"})
            return

        # Fix #8: re-read key at request time so it reflects the current env
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            self.send_json(500, {"error": "ANTHROPIC_API_KEY not set on server."})
            return

        # Fix #3: handle missing/empty body as 400, not 500
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            self.send_json(400, {"error": "Request body is required."})
            return

        try:
            raw = self.rfile.read(length)
        except Exception:
            self.send_json(400, {"error": "Failed to read request body."})
            return

        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            self.send_json(400, {"error": "Invalid JSON body."})
            return

        question = body.get("question", "").strip()
        if not question:
            self.send_json(400, {"error": "Missing 'question' field."})
            return

        # Fix #5: reject oversized questions
        if len(question) > MAX_QUESTION_LEN:
            self.send_json(400, {"error": f"Question must be {MAX_QUESTION_LEN} characters or fewer."})
            return

        try:
            students = fetch_students()
            answer   = ask_claude(question, students, api_key)
            self.send_json(200, {
                "question":      question,
                "answer":        answer,
                "student_count": len(students),
            })
        except Exception as e:
            import traceback
            traceback.print_exc()  # Fix #4: log internally, don't send trace to client
            self.send_json(500, {"error": "An internal server error occurred."})


if __name__ == "__main__":
    print(f"Starting server on port {PORT}...")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
