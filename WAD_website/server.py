"""Small local API and static file server for the Loan Application System."""

from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import unquote, urlsplit
import hashlib
import json
import secrets
import sqlite3
import time


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "loan_system.sqlite3"
SESSION_SECONDS = 60 * 60 * 24 * 7


def connect_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_db():
    with connect_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                mobile TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS loan_applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                application_id TEXT NOT NULL UNIQUE,
                user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                applicant_name TEXT NOT NULL,
                email TEXT NOT NULL,
                mobile TEXT NOT NULL,
                date_of_birth TEXT NOT NULL,
                address TEXT NOT NULL,
                loan_type TEXT NOT NULL,
                loan_amount REAL NOT NULL,
                tenure TEXT NOT NULL,
                monthly_income REAL NOT NULL,
                employment TEXT NOT NULL,
                document_names TEXT NOT NULL DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'Application Submitted',
                status_details TEXT NOT NULL DEFAULT '',
                submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
        application_columns = {row["name"] for row in db.execute("PRAGMA table_info(loan_applications)")}
        if "status_details" not in application_columns:
            db.execute("ALTER TABLE loan_applications ADD COLUMN status_details TEXT NOT NULL DEFAULT ''")


def hash_password(password, salt=None):
    salt_bytes = bytes.fromhex(salt) if salt else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt_bytes, 310_000)
    return digest.hex(), salt_bytes.hex()


class WebsiteHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        requested_path = unquote(urlsplit(self.path).path)
        if requested_path.startswith("/data/") or requested_path in ("/server.py", "/DATABASE_SETUP.md") or requested_path.startswith("/.git/"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if requested_path == "/api/profile":
            self.get_profile()
            return
        if requested_path == "/":
            self.path = "/layout%20(1).html"
        super().do_GET()

    def get_profile(self):
        with connect_db() as db:
            user = self.session_user(db)
            if not user:
                self.send_json(HTTPStatus.UNAUTHORIZED, {"error": "Please log in to view your profile."})
                return
            rows = db.execute("""
                SELECT application_id, applicant_name, email, mobile, date_of_birth, address,
                       loan_type, loan_amount, tenure, monthly_income, employment,
                       document_names, status, status_details, submitted_at
                FROM loan_applications
                WHERE user_id = ? OR email = ? COLLATE NOCASE
                ORDER BY submitted_at DESC, id DESC
            """, (user["id"], user["email"])).fetchall()
            applications = []
            for row in rows:
                application = dict(row)
                application["documents"] = json.loads(application.pop("document_names") or "[]")
                applications.append(application)
        self.send_json(HTTPStatus.OK, {
            "user": {"name": user["name"], "email": user["email"], "mobile": user["mobile"]},
            "applications": applications,
        })

    def send_json(self, status, payload, headers=None):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 1_000_000:
                raise ValueError
            value = json.loads(self.rfile.read(length))
            if not isinstance(value, dict):
                raise ValueError
            return value
        except (ValueError, json.JSONDecodeError):
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid request data."})
            return None

    def session_user(self, db):
        cookies = SimpleCookie(self.headers.get("Cookie", ""))
        morsel = cookies.get("loan_session")
        if not morsel:
            return None
        token_hash = hashlib.sha256(morsel.value.encode()).hexdigest()
        row = db.execute("""
            SELECT users.id, users.name, users.email, users.mobile
            FROM sessions JOIN users ON users.id = sessions.user_id
            WHERE sessions.token_hash = ? AND sessions.expires_at > ?
        """, (token_hash, int(time.time()))).fetchone()
        return row

    def do_POST(self):
        if self.path == "/api/register":
            self.register()
        elif self.path == "/api/login":
            self.login()
        elif self.path == "/api/logout":
            self.logout()
        elif self.path == "/api/applications":
            self.create_application()
        else:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "API endpoint not found."})

    def register(self):
        data = self.read_json()
        if data is None:
            return
        name = str(data.get("name", "")).strip()
        email = str(data.get("email", "")).strip().lower()
        mobile = str(data.get("mobile", "")).strip()
        password = data.get("password", "")
        if len(name) < 3 or "@" not in email or len(mobile) != 10 or not mobile.isdigit() or not isinstance(password, str) or len(password) < 6:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Enter a valid name, email, 10-digit mobile number, and password of at least 6 characters."})
            return
        password_hash, password_salt = hash_password(password)
        try:
            with connect_db() as db:
                db.execute("INSERT INTO users (name, email, mobile, password_hash, password_salt) VALUES (?, ?, ?, ?, ?)",
                           (name, email, mobile, password_hash, password_salt))
        except sqlite3.IntegrityError:
            self.send_json(HTTPStatus.CONFLICT, {"error": "An account with this email already exists."})
            return
        self.send_json(HTTPStatus.CREATED, {"message": "Registration successful. You can now log in."})

    def login(self):
        data = self.read_json()
        if data is None:
            return
        email = str(data.get("email", "")).strip().lower()
        password = data.get("password", "")
        with connect_db() as db:
            user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if not user or not isinstance(password, str):
                self.send_json(HTTPStatus.UNAUTHORIZED, {"error": "Email or password is incorrect."})
                return
            candidate_hash, _ = hash_password(password, user["password_salt"])
            if not secrets.compare_digest(candidate_hash, user["password_hash"]):
                self.send_json(HTTPStatus.UNAUTHORIZED, {"error": "Email or password is incorrect."})
                return
            token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            expires_at = int(time.time()) + SESSION_SECONDS
            db.execute("DELETE FROM sessions WHERE expires_at <= ?", (int(time.time()),))
            db.execute("INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)", (token_hash, user["id"], expires_at))
        cookie = f"loan_session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={SESSION_SECONDS}"
        self.send_json(HTTPStatus.OK, {"name": user["name"], "email": user["email"]}, {"Set-Cookie": cookie})

    def logout(self):
        with connect_db() as db:
            user = self.session_user(db)
            if user:
                cookies = SimpleCookie(self.headers.get("Cookie", ""))
                token_hash = hashlib.sha256(cookies["loan_session"].value.encode()).hexdigest()
                db.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
        cookie = "loan_session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"
        self.send_json(HTTPStatus.OK, {"message": "Logged out."}, {"Set-Cookie": cookie})

    def create_application(self):
        data = self.read_json()
        if data is None:
            return
        required = ("fullName", "email", "mobile", "dob", "address", "loanType", "tenure", "employment")
        if any(not str(data.get(field, "")).strip() for field in required):
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Please complete all required application fields."})
            return
        try:
            amount = float(data.get("loanAmount", 0))
            income = float(data.get("monthlyIncome", 0))
            if amount <= 0 or income <= 0:
                raise ValueError
        except (TypeError, ValueError):
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Loan amount and monthly income must be greater than zero."})
            return
        files = data.get("documents", [])
        if not isinstance(files, list):
            files = []
        document_names = json.dumps([str(item.get("fileName", ""))[:255] for item in files if isinstance(item, dict)])
        application_id = "LAS" + secrets.token_hex(4).upper()
        with connect_db() as db:
            user = self.session_user(db)
            if not user:
                user = db.execute("SELECT id FROM users WHERE email = ? COLLATE NOCASE", (str(data["email"]).strip(),)).fetchone()
            db.execute("""INSERT INTO loan_applications
                (application_id, user_id, applicant_name, email, mobile, date_of_birth, address, loan_type,
                 loan_amount, tenure, monthly_income, employment, document_names)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (application_id, user["id"] if user else None, str(data["fullName"]).strip(),
                 str(data["email"]).strip(), str(data["mobile"]).strip(), str(data["dob"]),
                 str(data["address"]).strip(), str(data["loanType"]), amount, str(data["tenure"]),
                 income, str(data["employment"]), document_names))
        self.send_json(HTTPStatus.CREATED, {"applicationId": application_id, "status": "Application Submitted"})


if __name__ == "__main__":
    initialize_db()
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), WebsiteHandler)
    browser_host = "localhost" if host in ("0.0.0.0", "::") else host
    print(f"Loan Application System running at http://{browser_host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.server_close()
