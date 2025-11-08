import json
from typing import Dict, Any
from datetime import datetime, timedelta
try:
    from models import Bill
except Exception:
    Bill = None

def prepare_monthly_spend_chart(agg: Dict[str, Any]) -> Dict[str, Any]:
    labels = agg['monthly']['labels']
    data = agg['monthly']['data']
    return {'type': 'line', 'data': {'labels': labels, 'datasets': [{'label': 'Total spend', 'data': data, 'borderColor': '#38A169', 'backgroundColor': 'rgba(56,161,105,0.08)', 'fill': True}]}, 'options': {'responsive': True, 'plugins': {'legend': {'display': True}}}}

def prepare_tag_breakdown_chart(agg: Dict[str, Any]) -> Dict[str, Any]:
    labels = agg['tag_breakdown']['labels']
    data = agg['tag_breakdown']['data']
    colors = ['#6366F1', '#10B981', '#FB923C', '#EF4444', '#60A5FA', '#A78BFA', '#F59E0B', '#6EE7B7']
    return {'type': 'doughnut', 'data': {'labels': labels, 'datasets': [{'data': data, 'backgroundColor': colors[:len(data)]}]}, 'options': {'responsive': True}}

def prepare_payment_mode_chart(agg: Dict[str, Any]) -> Dict[str, Any]:
    labels = agg['payment_mode_breakdown']['labels']
    data = agg['payment_mode_breakdown']['data']
    return {'type': 'bar', 'data': {'labels': labels, 'datasets': [{'label': 'By payment mode', 'data': data, 'backgroundColor': '#60A5FA'}]}, 'options': {'indexAxis': 'y', 'responsive': True}}

def prepare_created_history_chart(agg: Dict[str, Any]) -> Dict[str, Any]:
    labels = agg.get('created_history', {}).get('labels', [])
    data = agg.get('created_history', {}).get('data', [])
    return {'type': 'bar', 'data': {'labels': labels, 'datasets': [{'label': 'Bills created', 'data': data, 'backgroundColor': '#A78BFA'}]}, 'options': {'responsive': True}}

def prepare_cumulative_spend_chart(agg: Dict[str, Any]) -> Dict[str, Any]:
    labels = agg['monthly']['labels']
    data = agg['monthly']['data']
    cum = []
    s = 0.0
    for v in data:
        s += v
        cum.append(round(s, 2))
    return {'type': 'line', 'data': {'labels': labels, 'datasets': [{'label': 'Cumulative spend', 'data': cum, 'borderColor': '#F59E0B', 'backgroundColor': 'rgba(245,158,11,0.08)', 'fill': True}]}, 'options': {'responsive': True, 'plugins': {'legend': {'display': True}}}}

def prepare_all(agg: Dict[str, Any]) -> Dict[str, Any]:
    return {'monthly_spend': prepare_monthly_spend_chart(agg), 'cumulative_spend': prepare_cumulative_spend_chart(agg), 'tag_breakdown': prepare_tag_breakdown_chart(agg), 'payment_mode': prepare_payment_mode_chart(agg), 'created_history': prepare_created_history_chart(agg), 'raw': agg}

def prepare_and_store(agg: Dict[str, Any], user_id: str, db, AgentResult):
    payload = prepare_all(agg)
    try:
        timeline = []
        if Bill is not None:
            bills = db.session.query(Bill).filter(Bill.user_id == user_id).order_by(Bill.next_due.asc()).all()
        else:
            bills = []
        now = datetime.utcnow()
        for b in bills:
            if not b.next_due:
                continue
            try:
                nd = b.next_due
                if isinstance(nd, str):
                    ndt = datetime.fromisoformat(nd)
                else:
                    ndt = nd
            except Exception:
                continue
            if ndt.date() >= now.date() - timedelta(days=7) and ndt.date() <= now.date() + timedelta(days=90):
                timeline.append({'id': getattr(b, 'id', None), 'name': getattr(b, 'name', '')[:40], 'due_date': ndt.isoformat(), 'amount': (getattr(b, 'amount_cents', 0) or 0) / 100.0, 'tag': getattr(b, 'tag', None), 'payment_mode': getattr(b, 'payment_mode', None)})
        timeline = sorted(timeline, key=lambda x: x.get('due_date') or '')
        payload['upcoming_timeline'] = timeline[:12]
    except Exception:
        pass
    try:
        ar = AgentResult(agent_key='visual_prep_agent_v1', user_id=user_id, payload=json.dumps(payload))
        db.session.add(ar)
        db.session.commit()
    except Exception:
        db.session.rollback()
    return payload
if __name__ == '__main__':
    print('Use prepare_all(agg) to get Chart.js payloads')
