import uuid
from datetime import datetime
from db import db
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text


def generate_uuid():
    return str(uuid.uuid4())


class User(db.Model):
    __tablename__ = 'users'
    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'created_at': self.created_at.isoformat(),
        }


class Bill(db.Model):
    __tablename__ = 'bills'
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    tag = Column(String(100), nullable=True)
    payment_mode = Column(String(100), nullable=True)
    amount_cents = Column(Integer, nullable=False, default=0)
    period = Column(String(50), nullable=True)  # e.g., monthly, yearly
    last_paid = Column(DateTime, nullable=True)
    next_due = Column(DateTime, nullable=True)
    due_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'description': self.description,
            'tag': self.tag,
            'payment_mode': self.payment_mode,
            'amount_cents': self.amount_cents,
            'period': self.period,
            'last_paid': self.last_paid.isoformat() if self.last_paid else None,
            'next_due': self.next_due.isoformat() if self.next_due else None,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'created_at': self.created_at.isoformat(),
        }
