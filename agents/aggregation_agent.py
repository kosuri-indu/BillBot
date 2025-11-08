import json
import os
from collections import defaultdict, OrderedDict
from datetime import datetime, timedelta
from typing import Dict, Any

from models import Bill, AgentResult
from db import db

# If SUPABASE_URL and SUPABASE_KEY are present in env, prefer using Supabase
_USE_SUPABASE = bool(os.environ.get('SUPABASE_URL') and os.environ.get('SUPABASE_KEY'))
if _USE_SUPABASE:
    try:  
        from supabase import create_client
        _SUPABASE_URL = os.environ.get('SUPABASE_URL')
        _SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
        _supabase = create_client(_SUPABASE_URL, _SUPABASE_KEY)
    except Exception:
        _supabase = None
        _USE_SUPABASE = False


def _month_key(dt: datetime) -> str:
    return dt.strftime('%Y-%m')


def _shift_month(dt: datetime, months: int) -> datetime:
    """Return a new datetime representing the first day of the month shifted back by `months`.

    months=0 -> same month (first day). months=1 -> previous month first day, etc.
    """
    # normalize to first of month
    base = dt.replace(day=1)
    # compute zero-based month index
    idx = base.year * 12 + (base.month - 1) - months
    y = idx // 12
    m = (idx % 12) + 1
    return base.replace(year=y, month=m, day=1)


def aggregate_user_data(user_id: str, months: int = 12) -> Dict[str, Any]:
    """Aggregate bill/payment history for a user into time-series and breakdowns.

    This function avoids sending any PII to external services: it only works
    with numeric summaries and normalized category labels.
    """
    now = datetime.utcnow()

    # Build months_list for the last `months` months including the current month.
    # Example: months=12 on Nov 2025 -> ['2024-12', '2025-01', ..., '2025-11']
    months_list = []
    for back in range(months - 1, -1, -1):
        mdt = _shift_month(now, back)
        months_list.append(mdt.strftime('%Y-%m'))

    totals_by_month = OrderedDict((m, 0.0) for m in months_list)
    counts_by_month = OrderedDict((m, 0) for m in months_list)
    tag_totals = defaultdict(float)
    payment_mode_totals = defaultdict(float)
    created_counts = OrderedDict((m, 0) for m in months_list)

    # Query bills for user. Prefer Supabase when configured; otherwise use SQLAlchemy.
    records = []
    if _USE_SUPABASE and _supabase:
        try:
            resp = _supabase.table('bills').select('*').eq('user_id', user_id).execute()
            # supabase-py responses usually expose .data
            if hasattr(resp, 'data'):
                records = resp.data or []
            else:
                records = resp[0] if resp and isinstance(resp, (list, tuple)) else []
        except Exception:
            records = []
    else:
        bills = Bill.query.filter_by(user_id=user_id).all()
        for b in bills:
            records.append({
                'id': getattr(b, 'id', None),
                'name': getattr(b, 'name', None),
                'description': getattr(b, 'description', None),
                'tag': getattr(b, 'tag', None),
                'payment_mode': getattr(b, 'payment_mode', None),
                'amount_cents': getattr(b, 'amount_cents', 0),
                'last_paid': getattr(b, 'last_paid', None).isoformat() if getattr(b, 'last_paid', None) else None,
                'created_at': getattr(b, 'created_at', None).isoformat() if getattr(b, 'created_at', None) else None,
            })

    for r in records:
        # normalize dates from supabase (ISO strings) or the SQLAlchemy fallback
        lp = r.get('last_paid')
        ca = r.get('created_at')
        date = None
        if lp:
            try:
                date = datetime.fromisoformat(lp) if isinstance(lp, str) else lp
            except Exception:
                date = None
        if not date and ca:
            try:
                date = datetime.fromisoformat(ca) if isinstance(ca, str) else ca
            except Exception:
                date = None
        if not date:
            continue

        mkey = _month_key(date)
        amount = (r.get('amount_cents') or 0) / 100.0

        if mkey in totals_by_month:
            totals_by_month[mkey] += amount
            counts_by_month[mkey] += 1

        tag_key = (r.get('tag') or 'Uncategorized')
        pm_key = (r.get('payment_mode') or 'Unknown')
        tag_totals[tag_key] += amount
        payment_mode_totals[pm_key] += amount

        created_key = None
        if ca:
            try:
                created_dt = datetime.fromisoformat(ca) if isinstance(ca, str) else ca
                created_key = _month_key(created_dt)
            except Exception:
                created_key = None
        if created_key in created_counts:
            created_counts[created_key] += 1

    # convert OrderedDicts to lists for JSON
    monthly = {
        'labels': list(totals_by_month.keys()),
        'data': [round(v, 2) for v in totals_by_month.values()],
        'counts': [counts_by_month[k] for k in totals_by_month.keys()]
    }

    tag_breakdown = {
        'labels': list(tag_totals.keys()),
        'data': [round(v, 2) for v in tag_totals.values()]
    }

    payment_mode_breakdown = {
        'labels': list(payment_mode_totals.keys()),
        'data': [round(v, 2) for v in payment_mode_totals.values()]
    }

    created_history = {
        'labels': list(created_counts.keys()),
        'data': [created_counts[k] for k in created_counts.keys()]
    }

    payload = {
        'generated_at': datetime.utcnow().isoformat(),
        'monthly': monthly,
        'tag_breakdown': tag_breakdown,
        'payment_mode_breakdown': payment_mode_breakdown,
        'created_history': created_history,
    }

    # store result in DB (AgentResult) for caching / history
    try:
        ar = AgentResult(agent_key='aggregation_agent_v1', user_id=user_id, payload=json.dumps(payload))
        db.session.add(ar)
        db.session.commit()
    except Exception:
        # don't fail on storage errors; return payload nonetheless
        db.session.rollback()

    return payload


if __name__ == '__main__':
    print('This module provides aggregate_user_data(user_id, months=12)')
