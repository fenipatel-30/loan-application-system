# Run the website with its database

The website uses a local SQLite database. Python creates `data/loan_system.sqlite3` and its tables the first time the server starts. No external package installation is needed.

1. Open PowerShell in this project folder.
2. Run `python server.py` (on Windows, `py server.py` also works).
3. Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

Registration creates a database account, login verifies it and starts a session, and loan applications are saved to the database. After login, the site opens the profile page, which shows the account details and applications associated with that account. Each application starts with the status `Application Submitted`; the profile displays any later status and status details saved in the database. Passwords are stored as salted PBKDF2 hashes. Uploaded documents are not stored by this local setup; only their filenames are recorded. Keep the website open through this server so the frontend can reach the database API.
