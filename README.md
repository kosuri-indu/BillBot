# BillBot

This project is a small Flask app. These notes explain how to configure and test a MySQL connection.

## Setup (Python environment)

1. Create a virtual environment and activate it:

   Windows PowerShell:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Install the Python dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

## Configure MySQL

You can use a local MySQL server or a hosted MySQL instance. Set the following environment variables to enable MySQL (otherwise the app falls back to a development SQLite DB):

- `MYSQL_USER` — database username
- `MYSQL_PASSWORD` — database password
- `MYSQL_HOST` — host (defaults to `127.0.0.1`)
- `MYSQL_PORT` — port (defaults to `3306`)
- `MYSQL_DB` — database name

Example (PowerShell):

```powershell
$env:MYSQL_USER = 'myuser'; $env:MYSQL_PASSWORD = 'mypassword'; $env:MYSQL_HOST = '127.0.0.1'; $env:MYSQL_DB = 'billbot_db'
```

If you don't set these, the app will use `sqlite:///billbot_dev.db` for quick local testing.

## Run the app

```powershell
python app.py
```

Open `http://127.0.0.1:5000/db-test` to verify database connectivity. The endpoint will create a simple sample row if one does not exist and return it in JSON.

## Notes

- For production use, prefer using migrations (e.g. Flask-Migrate / Alembic) instead of `create_all()`.
- On Windows, using `PyMySQL` avoids the need to compile `mysqlclient`.
