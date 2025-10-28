import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, Response
from dotenv import load_dotenv
from db import init_db, db
from werkzeug.security import generate_password_hash, check_password_hash
from models import User, Bill
from datetime import datetime
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
                next_due = last_paid.replace(day=min(last_paid.day, 28))  # Handle months with fewer days
                next_due = next_due.replace(month=next_due.month + 1 if next_due.month < 12 else 1,
                                          year=next_due.year + 1 if next_due.month == 12 else next_due.year)
            elif period == 'yearly':
                next_due = last_paid.replace(year=last_paid.year + 1)
            # For one-time, no next due date
        except Exception:
            last_paid = None

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
        due_date=next_due,  # Keep due_date for backward compatibility
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
    if first_payment_date:
        try:
            last_paid = datetime.fromisoformat(first_payment_date)
            # Recalculate next due date based on period
            if period == 'monthly':
                next_due = last_paid.replace(day=min(last_paid.day, 28))
                next_due = next_due.replace(month=next_due.month + 1 if next_due.month < 12 else 1,
                                          year=next_due.year + 1 if next_due.month == 12 else next_due.year)
            elif period == 'yearly':
                next_due = last_paid.replace(year=last_paid.year + 1)
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


@app.route('/profile')
def profile():
    user = get_current_user()
    if not user:
        return redirect(url_for('index'))
    session['user_email'] = user.email  # Store email in session for template
    return render_template('profile.html')


@app.route('/update-profile', methods=['POST'])
def update_profile():
    user = get_current_user()
    if not user:
        return redirect(url_for('index'))

    email = request.form.get('email')
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')

    # Verify current password
    if not check_password_hash(user.password_hash, current_password):
        flash('Current password is incorrect.', 'error')
        return redirect(url_for('profile'))

    # Check if email is being changed and if it's already taken
    if email != user.email:
        existing = User.query.filter_by(email=email).first()
        if existing:
            flash('Email already registered.', 'error')
            return redirect(url_for('profile'))
        user.email = email

    # Update password if provided
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

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow(['Name', 'Description', 'Tag', 'Payment Mode', 'Amount', 'Period', 'Last Paid', 'Next Due', 'Created At'])

    # Write data
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

    # Delete all bills first (due to foreign key constraint)
    Bill.query.filter_by(user_id=user.id).delete()

    # Delete the user
    db.session.delete(user)
    db.session.commit()

    # Clear session
    session.clear()

    flash('Account deleted successfully.', 'info')
    return redirect(url_for('index'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='127.0.0.1', port=5000)
