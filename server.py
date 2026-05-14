"""
server.py - Student Agent backend for Render
"""

import os
import csv
import json
import io
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
SHEET_URL = "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit?usp=sharing&output=csv"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
PORT = int(os.environ.get("PORT", 8000))    


def fetch_students():
    req = urllib.request.Request(SHEET_URL, headers={"User-Agent": "Mozilla/5.0"})
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
    return students


def ask_claude(question, students):
    payload = json.dumps({
        "model": "claude-sonnet-4-20250514",
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
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read())["content"][0]["text"]


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
        try:
            length   = int(self.headers.get("Content-Length", 0))
            body     = json.loads(self.rfile.read(length))
            question = body.get("question", "").strip()

            if not question:
                self.send_json(400, {"error": "Missing 'question' field."})
                return

            if not ANTHROPIC_API_KEY:
                self.send_json(500, {"error": "ANTHROPIC_API_KEY not set on server."})
                return

            students = fetch_students()
            answer   = ask_claude(question, students)
            self.send_json(200, {
                "question":      question,
                "answer":        answer,
                "student_count": len(students),
            })
        except Exception as e:
            self.send_json(500, {"error": str(e)})


if __name__ == "__main__":
    print(f"Starting server on port {PORT}...")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
