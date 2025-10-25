import os
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__, static_folder='static', template_folder='templates')

# Database configuration using environment variables. If MYSQL_* vars aren't set,
# fall back to a local SQLite file for convenience.
mysql_user = os.environ.get('MYSQL_USER')
mysql_password = os.environ.get('MYSQL_PASSWORD')
mysql_host = os.environ.get('MYSQL_HOST', '127.0.0.1')
mysql_port = os.environ.get('MYSQL_PORT', '3306')
mysql_db = os.environ.get('MYSQL_DB')

if mysql_user and mysql_password and mysql_db:
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        f"mysql+pymysql://{mysql_user}:{mysql_password}@{mysql_host}:{mysql_port}/{mysql_db}"
    )
else:
    # Helpful fallback for development without MySQL
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///billbot_dev.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


class Bill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)

    def to_dict(self):
        return {'id': self.id, 'description': self.description, 'amount': self.amount}


def create_tables():
    # Create tables if they don't exist. For production, use migrations instead.
    db.create_all()


@app.route('/')
def home():
    try:
        from sqlalchemy import text
        db.session.execute(text('SELECT 1'))
        db_status = "Database connection successful! ✅"
    except Exception as e:
        db_status = f"Database error: {str(e)} ❌"
    return f"Welcome to the BillBot!\n\nStatus: {db_status}"


@app.route('/db-test')
def db_test():
    """Simple endpoint to test DB connectivity. Returns one Bill sample (creates one if empty)."""
    try:
        bill = Bill.query.first()
        if not bill:
            bill = Bill(description='Test bill', amount=0.0)
            db.session.add(bill)
            db.session.commit()
        return jsonify({'status': 'ok', 'sample': bill.to_dict()})
    except Exception as e:
        # Return error details to help debugging local setup
        return jsonify({'status': 'error', 'error': str(e)}), 500


if __name__ == '__main__':
    # Ensure tables are created when running the app directly. Using an explicit
    # application context avoids relying on `before_first_request`, which may not
    # be present in all Flask versions/configurations.
    with app.app_context():
        create_tables()

    app.run(debug=True, host='127.0.0.1', port=5000)
