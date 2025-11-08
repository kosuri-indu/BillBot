from typing import Dict, Any
from models import Bill
from db import db
from datetime import datetime, timedelta

def aggregate_user_data(user_id: str, months: int = 12) -> Dict[str, Any]:
    """Collect billing data for the user and produce lightweight aggregates.

    This function is intentionally deterministic (no LLM). It returns a dict
    that other agents (LangChain-backed or fallback) can consume.
    """
    now = datetime.utcnow()
    start = now - timedelta(days=30 * months)
    bills = Bill.query.filter_by(user_id=user_id).all()
    bill_list = [b.to_dict() for b in bills]

    total_cents = sum(b.amount_cents for b in bills) if bills else 0
    by_tag = {}
    for b in bills:
        tag = b.tag or 'other'
        by_tag.setdefault(tag, 0)
        by_tag[tag] += (b.amount_cents or 0)

    # simple top bills
    top_bills = sorted(bill_list, key=lambda x: x.get('amount_cents', 0), reverse=True)[:5]

    return {
        'user_id': user_id,
        'months': months,
        'start': start.isoformat(),
        'end': now.isoformat(),
        'total_cents': total_cents,
        'by_tag_cents': by_tag,
        'top_bills': top_bills,
        'bills': bill_list,
    }
