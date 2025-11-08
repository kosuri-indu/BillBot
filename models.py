import uuid
from datetime import datetime
from db import db
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Boolean

def generate_uuid():
    return str(uuid.uuid4())

class User(db.Model):
    __tablename__ = 'users'
    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {'id': self.id, 'email': self.email, 'created_at': self.created_at.isoformat()}

class Bill(db.Model):
    __tablename__ = 'bills'
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    tag = Column(String(100), nullable=True)
    payment_mode = Column(String(100), nullable=True)
    amount_cents = Column(Integer, nullable=False, default=0)
    tag_id = Column(String(36), ForeignKey('tags.id'), nullable=True)
    default_payment_mode_id = Column(String(36), ForeignKey('payment_modes.id'), nullable=True)
    currency = Column(String(10), nullable=False, default='INR')
    schedule_type = Column(String(32), nullable=True)
    interval_count = Column(Integer, nullable=False, default=1)
    interval_unit = Column(String(16), nullable=False, default='months')
    active = Column(Boolean, nullable=False, default=True)
    period = Column(String(50), nullable=True)
    last_paid = Column(DateTime, nullable=True)
    next_due = Column(DateTime, nullable=True)
    due_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {'id': self.id, 'user_id': self.user_id, 'name': self.name, 'description': self.description, 'tag': self.tag, 'payment_mode': self.payment_mode, 'amount_cents': self.amount_cents, 'period': self.period, 'last_paid': self.last_paid.isoformat() if self.last_paid else None, 'next_due': self.next_due.isoformat() if self.next_due else None, 'due_date': self.due_date.isoformat() if self.due_date else None, 'created_at': self.created_at.isoformat()}

class Tag(db.Model):
    __tablename__ = 'tags'
    id = Column(String(36), primary_key=True, default=generate_uuid)
    key = Column(String(100), unique=True, nullable=False)
    label = Column(String(255), nullable=False)
    color_class = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class PaymentMode(db.Model):
    __tablename__ = 'payment_modes'
    id = Column(String(36), primary_key=True, default=generate_uuid)
    key = Column(String(100), unique=True, nullable=False)
    label = Column(String(255), nullable=False)
    color_class = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Agent(db.Model):
    __tablename__ = 'agents'
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False)
    bill_id = Column(String(36), ForeignKey('bills.id'), nullable=True)
    type = Column(String(32), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    config = Column(Text, nullable=True)
    schedule = Column(String(255), nullable=True)
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True)

class AgentRun(db.Model):
    __tablename__ = 'agent_runs'
    id = Column(String(36), primary_key=True, default=generate_uuid)
    agent_id = Column(String(36), ForeignKey('agents.id'), nullable=False)
    run_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(32), nullable=True)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

def seed_defaults(app=None):
    created = 0
    if app:
        ctx = app.app_context()
        ctx.push()
    try:
        defaults = [('credit_card', 'Credit Card', 'bg-blue-600 text-white'), ('debit_card', 'Debit Card', 'bg-sky-600 text-white'), ('upi', 'UPI', 'bg-emerald-600 text-white'), ('bank_transfer', 'Bank Transfer', 'bg-indigo-600 text-white'), ('netbanking', 'Netbanking', 'bg-violet-600 text-white'), ('wallet', 'Wallet', 'bg-amber-500 text-gray-900'), ('cash', 'Cash', 'bg-lime-600 text-gray-900'), ('other', 'Other', 'bg-gray-600 text-white')]
        for key, label, color in defaults:
            existing = PaymentMode.query.filter_by(key=key).first()
            if not existing:
                pm = PaymentMode(key=key, label=label, color_class=color)
                db.session.add(pm)
                created += 1
        tag_defaults = [('rent', 'Rent', 'bg-indigo-700 text-white'), ('groceries', 'Groceries', 'bg-emerald-600 text-white'), ('internet', 'Internet', 'bg-violet-600 text-white'), ('electricity', 'Electricity', 'bg-yellow-600 text-gray-900'), ('other', 'Other', 'bg-gray-600 text-white')]
        for key, label, color in tag_defaults:
            existing = Tag.query.filter_by(key=key).first()
            if not existing:
                t = Tag(key=key, label=label, color_class=color)
                db.session.add(t)
                created += 1
        if created:
            db.session.commit()
    finally:
        if app:
            ctx.pop()

class AgentResult(db.Model):
    __tablename__ = 'agent_results'
    id = Column(String(36), primary_key=True, default=generate_uuid)
    agent_key = Column(String(128), nullable=False, index=True)
    user_id = Column(String(36), nullable=True, index=True)
    payload = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {'id': self.id, 'agent_key': self.agent_key, 'user_id': self.user_id, 'payload': self.payload, 'created_at': self.created_at.isoformat()}
