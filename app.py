import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, Response, jsonify
from dotenv import load_dotenv
from db import init_db, db
from werkzeug.security import generate_password_hash, check_password_hash
from models import User, Bill, seed_defaults, AgentResult
from datetime import datetime
import csv
import io
import json
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError
from threading import Thread

def _compute_next_due_from(start_date, period, interval_count=1):
    if not start_date:
        return None
    now = datetime.utcnow()
    try:
        cur = start_date
    except Exception:
        return None
    max_iterations = 1200
    i = 0
    if period == 'one-time' or not period:
        return cur if cur >= now else None
    while cur < now and i < max_iterations:
        if period == 'monthly':
            month = cur.month - 1 + interval_count
            year = cur.year + month // 12
            month = month % 12 + 1
            day = min(cur.day, 28)
            try:
                cur = cur.replace(year=year, month=month, day=day)
            except Exception:
                cur = cur.replace(day=1)
                if month == 12:
                    cur = cur.replace(year=year + 1, month=1)
                else:
                    cur = cur.replace(month=month)
        elif period == 'yearly':
            try:
                cur = cur.replace(year=cur.year + interval_count)
            except Exception:
                cur = cur.replace(month=cur.month, day=min(cur.day, 28), year=cur.year + interval_count)
        else:
            return None
        i += 1
    return cur if cur >= now else None
from agents import aggregation_agent, visual_prep_agent, narration_agent
from agents import scheduler as agents_scheduler
load_dotenv()
app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret')
init_db(app)

def _run_agents_background(user_id: str):
    with app.app_context():
        try:
            agg = aggregation_agent.aggregate_user_data(user_id, months=12)
            try:
                visual_prep_agent.prepare_and_store(agg, user_id, db, AgentResult)
            except Exception:
                pass
            try:
                narration = narration_agent.generate_narration(agg, user_id=user_id)
                ar = AgentResult(agent_key='narration_agent_v1', user_id=user_id, payload=json.dumps(narration))
                db.session.add(ar)
                db.session.commit()
            except Exception:
                db.session.rollback()
        except Exception:
            pass

@app.route('/api/overview/trigger-refresh', methods=['POST'])
def api_overview_trigger_refresh():
    user = get_current_user()
    if not user:
        return (jsonify({'error': 'authentication required'}), 401)
    Thread(target=_run_agents_background, args=(user.id,)).start()
    return (jsonify({'status': 'accepted'}), 202)

def get_current_user():
    user_id = session.get('user_id')
    if not user_id:
        return None
    return User.query.get(user_id)

@app.route('/')
def index():
    return render_template('auth_ui.html')

@app.route('/signup', methods=['POST'])
def signup():
    email = request.form.get('signupEmail')
    password = request.form.get('signupPassword')
    if not email or not password:
        flash('Email and password are required.', 'error')
        return redirect(url_for('index'))
    existing = User.query.filter_by(email=email).first()
    if existing:
        flash('Email already registered. Please log in.', 'error')
        return redirect(url_for('index'))
    user = User(email=email, password_hash=generate_password_hash(password))
    db.session.add(user)
    db.session.commit()
    session['user_id'] = user.id
    flash('Account created. Welcome!', 'success')
    return redirect(url_for('overview'))

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('loginEmail')
    password = request.form.get('loginPassword')
    user = User.query.filter_by(email=email).first()
    if not user:
        flash('No account found with this email. Please create an account first.', 'error')
        return redirect(url_for('index'))
    if not check_password_hash(user.password_hash, password):
        flash('Invalid password. Please try again.', 'error')
        return redirect(url_for('index'))
    session['user_id'] = user.id
    flash('Logged in successfully.', 'success')
    return redirect(url_for('overview'))

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/overview')
def overview():
    user = get_current_user()
    if not user:
        return redirect(url_for('index'))
    return render_template('overview.html')

@app.route('/bills', methods=['GET'])
def bills():
    user = get_current_user()
    if not user:
        return redirect(url_for('index'))
    bills = Bill.query.filter_by(user_id=user.id).order_by(Bill.next_due.asc().nulls_last()).all()
    now = datetime.utcnow()
    for b in bills:
        try:
            nd = getattr(b, 'next_due', None)
            if not nd or (isinstance(nd, datetime) and nd < now):
                base = getattr(b, 'last_paid', None) or getattr(b, 'created_at', None)
                computed = None
                if base:
                    try:
                        computed = _compute_next_due_from(base, getattr(b, 'period', None), interval_count=1)
                    except Exception:
                        computed = None
                if computed:
                    b.next_due = computed
        except Exception:
            continue
    return render_template('bills.html', bills=bills)

@app.route('/bills/create', methods=['POST'])
def create_bill():
    user = get_current_user()
    if not user:
        return redirect(url_for('index'))
    name = request.form.get('name')
    description = request.form.get('description')
    tag = request.form.get('tag')
    payment_mode = request.form.get('payment_mode')
    amount = request.form.get('amount')
    period = request.form.get('period')
    first_payment_date = request.form.get('first_payment_date')
    try:
        amount_cents = int(float(amount) * 100)
    except Exception:
        amount_cents = 0
    last_paid = None
    next_due = None
    if first_payment_date:
        try:
            last_paid = datetime.fromisoformat(first_payment_date)
            next_due = _compute_next_due_from(last_paid, period, interval_count=1)
        except Exception:
            last_paid = None
    bill = Bill(user_id=user.id, name=name, description=description, tag=tag, payment_mode=payment_mode, amount_cents=amount_cents, period=period, last_paid=last_paid, next_due=next_due, due_date=next_due)
    db.session.add(bill)
    db.session.commit()
    flash('Bill created.', 'success')
    try:
        Thread(target=_run_agents_background, args=(user.id,)).start()
    except Exception:
        pass
    return redirect(url_for('bills'))

@app.route('/bills/<bill_id>/edit', methods=['POST'])
def edit_bill(bill_id):
    user = get_current_user()
    if not user:
        return redirect(url_for('index'))
    bill = Bill.query.filter_by(id=bill_id, user_id=user.id).first()
    if not bill:
        flash('Bill not found.', 'error')
        return redirect(url_for('bills'))
    name = request.form.get('name')
    description = request.form.get('description')
    tag = request.form.get('tag')
    payment_mode = request.form.get('payment_mode')
    amount = request.form.get('amount')
    period = request.form.get('period')
    first_payment_date = request.form.get('first_payment_date')
    try:
        amount_cents = int(float(amount) * 100)
    except Exception:
        amount_cents = 0
    last_paid = bill.last_paid
    next_due = bill.next_due
    if first_payment_date:
        try:
            last_paid = datetime.fromisoformat(first_payment_date)
            next_due = _compute_next_due_from(last_paid, period, interval_count=1)
        except Exception:
            pass
    bill.name = name
    bill.description = description
    bill.tag = tag
    bill.payment_mode = payment_mode
    bill.amount_cents = amount_cents
    bill.period = period
    bill.last_paid = last_paid
    bill.next_due = next_due
    bill.due_date = next_due
    db.session.commit()
    flash('Bill updated.', 'success')
    try:
        Thread(target=_run_agents_background, args=(user.id,)).start()
    except Exception:
        pass
    return redirect(url_for('bills'))

@app.route('/bills/<bill_id>/delete', methods=['POST'])
def delete_bill(bill_id):
    user = get_current_user()
    if not user:
        return redirect(url_for('index'))
    bill = Bill.query.filter_by(id=bill_id, user_id=user.id).first()
    if not bill:
        flash('Bill not found.', 'error')
        return redirect(url_for('bills'))
    db.session.delete(bill)
    db.session.commit()
    flash('Bill deleted.', 'success')
    try:
        Thread(target=_run_agents_background, args=(user.id,)).start()
    except Exception:
        pass
    return redirect(url_for('bills'))

@app.route('/profile')
def profile():
    user = get_current_user()
    if not user:
        return redirect(url_for('index'))
    session['user_email'] = user.email
    return render_template('profile.html')

@app.route('/update-profile', methods=['POST'])
def update_profile():
    user = get_current_user()
    if not user:
        return redirect(url_for('index'))
    email = request.form.get('email')
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    if not check_password_hash(user.password_hash, current_password):
        flash('Current password is incorrect.', 'error')
        return redirect(url_for('profile'))
    if email != user.email:
        existing = User.query.filter_by(email=email).first()
        if existing:
            flash('Email already registered.', 'error')
            return redirect(url_for('profile'))
        user.email = email
    if new_password:
        user.password_hash = generate_password_hash(new_password)
    db.session.commit()
    flash('Profile updated successfully.', 'success')
    return redirect(url_for('profile'))

@app.route('/settings')
def settings():
    user = get_current_user()
    if not user:
        return redirect(url_for('index'))
    return render_template('settings.html')

@app.route('/export-data')
def export_data():
    user = get_current_user()
    if not user:
        return redirect(url_for('index'))
    bills = Bill.query.filter_by(user_id=user.id).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Name', 'Description', 'Tag', 'Payment Mode', 'Amount', 'Period', 'Last Paid', 'Next Due', 'Created At'])
    for bill in bills:
        writer.writerow([bill.name, bill.description or '', bill.tag or '', bill.payment_mode or '', f'₹{bill.amount_cents / 100:.2f}', bill.period or '', bill.last_paid.strftime('%Y-%m-%d') if bill.last_paid else '', bill.next_due.strftime('%Y-%m-%d') if bill.next_due else '', bill.created_at.strftime('%Y-%m-%d %H:%M:%S')])
    output.seek(0)
    return Response(output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': f"attachment; filename=billbot_data_{datetime.now().strftime('%Y%m%d')}.csv"})

@app.route('/api/overview/data')
def api_overview_data():
    user = get_current_user()
    if not user:
        return (jsonify({'error': 'authentication required'}), 401)
    vp_row = AgentResult.query.filter_by(agent_key='visual_prep_agent_v1', user_id=user.id).order_by(AgentResult.created_at.desc()).first()
    n_row = AgentResult.query.filter_by(agent_key='narration_agent_v1', user_id=user.id).order_by(AgentResult.created_at.desc()).first()
    charts = None
    narration = None
    try:
        if vp_row:
            charts = json.loads(vp_row.payload)
    except Exception:
        charts = None
    try:
        if n_row:
            narration = json.loads(n_row.payload)
    except Exception:
        narration = None
    latest_bill = Bill.query.filter_by(user_id=user.id).order_by(Bill.created_at.desc()).first()
    needs_recompute = False
    if latest_bill:
        latest_ts = latest_bill.created_at
        if not vp_row or (vp_row and vp_row.created_at < latest_ts) or (not n_row) or (n_row and n_row.created_at < latest_ts):
            needs_recompute = True
    try:
        force = request.args.get('force')
        if force and str(force).lower() in ('1', 'true', 'yes'):
            needs_recompute = True
    except Exception:
        pass
    if needs_recompute or charts is None or narration is None:
        agg = aggregation_agent.aggregate_user_data(user.id, months=12)
        try:
            charts = visual_prep_agent.prepare_and_store(agg, user.id, db, AgentResult)
        except Exception:
            try:
                charts = visual_prep_agent.prepare_all(agg)
            except Exception:
                charts = None
        try:
            narration = narration_agent.generate_narration(agg, user_id=user.id)
            try:
                ar = AgentResult(agent_key='narration_agent_v1', user_id=user.id, payload=json.dumps(narration))
                db.session.add(ar)
                db.session.commit()
            except Exception:
                db.session.rollback()
        except Exception:
            narration = narration or {'summary': 'No insights available.', 'bullets': [], 'top_changes': []}
    return jsonify({'charts': charts, 'narration': narration})

@app.route('/delete-account', methods=['POST'])
def delete_account():
    user = get_current_user()
    if not user:
        return redirect(url_for('index'))
    Bill.query.filter_by(user_id=user.id).delete()
    db.session.delete(user)
    db.session.commit()
    session.clear()
    flash('Account deleted successfully.', 'info')
    return redirect(url_for('index'))
if __name__ == '__main__':

    def safe_startup():
        try:
            with app.app_context():
                with db.engine.connect() as conn:
                    conn.execute(text('SELECT 1'))
        except OperationalError as e:
            print('Database connection failed:', e)
            current_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
            if current_uri and current_uri.startswith('sqlite'):
                print('SQLite database configured but connection failed. Exiting.')
                raise
            fallback = 'sqlite:///dev_fallback.db'
            print(f'Falling back to local SQLite DB at {fallback}')
            app.config['SQLALCHEMY_DATABASE_URI'] = fallback
            db.init_app(app)
        with app.app_context():
            try:
                db.create_all()
            except Exception as e:
                print('Error during db.create_all():', e)
            inspector = inspect(db.engine)
            try:
                cols = {c['name'] for c in inspector.get_columns('bills')}
            except Exception:
                cols = set()
            is_sqlite = str(db.engine.url).startswith('sqlite')
            if is_sqlite:
                want = {'tag_id': 'TEXT', 'default_payment_mode_id': 'TEXT', 'currency': "TEXT DEFAULT 'INR'", 'schedule_type': 'TEXT', 'interval_count': 'INTEGER', 'interval_unit': "TEXT DEFAULT 'months'", 'active': 'BOOLEAN', 'period': 'TEXT', 'last_paid': 'DATETIME', 'next_due': 'DATETIME', 'due_date': 'DATETIME', 'created_at': 'DATETIME'}
            else:
                want = {'tag_id': 'VARCHAR(36)', 'default_payment_mode_id': 'VARCHAR(36)', 'currency': "VARCHAR(10) DEFAULT 'INR'", 'schedule_type': 'VARCHAR(32)', 'interval_count': 'INTEGER DEFAULT 1', 'interval_unit': "VARCHAR(16) DEFAULT 'months'", 'active': 'BOOLEAN DEFAULT true', 'period': 'VARCHAR(50)', 'last_paid': 'TIMESTAMP', 'next_due': 'TIMESTAMP', 'due_date': 'TIMESTAMP', 'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'}
            with db.engine.begin() as conn:
                for col, coltype in want.items():
                    if col not in cols:
                        stmt = text(f'ALTER TABLE bills ADD COLUMN {col} {coltype}')
                        try:
                            conn.execute(stmt)
                            print(f'Added missing column bills.{col}')
                        except Exception as e:
                            print(f'Could not add column {col}:', e)
            try:
                pm_cols = {c['name'] for c in inspector.get_columns('payment_modes')}
            except Exception:
                pm_cols = set()
            if 'color_class' not in pm_cols:
                coltype = 'TEXT' if is_sqlite else 'VARCHAR(64)'
                try:
                    with db.engine.begin() as conn:
                        conn.execute(text(f'ALTER TABLE payment_modes ADD COLUMN color_class {coltype}'))
                        print('Added missing column payment_modes.color_class')
                except Exception as e:
                    print('Could not add payment_modes.color_class:', e)
            try:
                seed_defaults(app)
            except Exception as e:
                print('Warning: seed_defaults failed during startup:', e)
    safe_startup()
    try:
        agents_scheduler.start(period_minutes=15)
    except Exception as e:
        print('Could not start agent scheduler:', e)
    app.run(debug=True, host='127.0.0.1', port=5000)
