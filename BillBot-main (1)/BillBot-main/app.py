import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, Response, jsonify # <-- ADD jsonify
from dotenv import load_dotenv
from db import init_db, db
from werkzeug.security import generate_password_hash, check_password_hash
from models import User, Bill
from datetime import datetime
from dateutil.relativedelta import relativedelta # <-- NEW IMPORT
import csv
import io

load_dotenv()

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret')

init_db(app)

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
        # convert amount to cents
        amount_cents = int(float(amount) * 100)
    except Exception:
        amount_cents = 0

    last_paid = None
    next_due = None
    if first_payment_date:
        try:
            last_paid = datetime.fromisoformat(first_payment_date)
            
            # Calculate next due date based on period
            if period == 'monthly':
                # CRITICAL FIX: Ensure 'next_due' calculation correctly steps forward from 'last_paid'
                next_due = last_paid + relativedelta(months=+1)
            elif period == 'yearly':
                next_due = last_paid + relativedelta(years=+1)
            # For one-time, next_due remains None (or set it to last_paid if it's the only time)
            elif period == 'one-time':
                next_due = last_paid
            
        except Exception:
            last_paid = None
            next_due = None

    bill = Bill(
        user_id=user.id,
        name=name,
        description=description,
        tag=tag,
        payment_mode=payment_mode,
        amount_cents=amount_cents,
        period=period,
        last_paid=last_paid,
        next_due=next_due,
        due_date=next_due, 
    )
    db.session.add(bill)
    db.session.commit()
    flash('Bill created.', 'success')
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
    
    # Recalculate next due date if a new 'first_payment_date' (last_paid date) is provided
    if first_payment_date:
        try:
            last_paid = datetime.fromisoformat(first_payment_date)
            
            if period == 'monthly':
                next_due = last_paid + relativedelta(months=+1)
            elif period == 'yearly':
                next_due = last_paid + relativedelta(years=+1)
            elif period == 'one-time':
                 next_due = last_paid
                 
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
    return redirect(url_for('bills'))

# --- NEW CRITICAL API ROUTE ---
@app.route('/api/v1/bills/due', methods=['GET'])
def api_bills_due():
    user = get_current_user()
    if not user:
        return jsonify([]), 401 

    # 1. Define the 30-day window
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    thirty_days_from_now = today + relativedelta(days=+30)
    
    # 2. Query bills: Must be for the current user, have a next_due date,
    # and fall within the 30-day window (inclusive of today).
    due_bills = Bill.query.filter(
        (Bill.user_id == user.id),
        (Bill.next_due != None),
        (Bill.next_due >= today),
        (Bill.next_due <= thirty_days_from_now)
    ).order_by(Bill.next_due.asc()).all()

    # 3. Format the data for JavaScript
    bills_data = []
    for bill in due_bills:
        bills_data.append({
            'id': bill.id,
            'name': bill.name,
            # Convert amount from cents back to the standard unit for the frontend
            'amount': bill.amount_cents / 100.0, 
            'tag': bill.tag,
            'period': bill.period,
            # Format date as a clean ISO string (YYYY-MM-DD)
            'dueDate': bill.next_due.strftime('%Y-%m-%d'),
            'next_due': bill.next_due.strftime('%Y-%m-%d')
        })
    
    return jsonify(bills_data)

# --- END NEW CRITICAL API ROUTE ---

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
        writer.writerow([
            bill.name,
            bill.description or '',
            bill.tag or '',
            bill.payment_mode or '',
            f"${bill.amount_cents / 100:.2f}",
            bill.period or '',
            bill.last_paid.strftime('%Y-%m-%d') if bill.last_paid else '',
            bill.next_due.strftime('%Y-%m-%d') if bill.next_due else '',
            bill.created_at.strftime('%Y-%m-%d %H:%M:%S')
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=billbot_data_{datetime.now().strftime("%Y%m%d")}.csv'}
    )


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
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='127.0.0.1', port=5000)