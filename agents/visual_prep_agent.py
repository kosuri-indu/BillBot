from typing import Dict, Any
from datetime import datetime


def _parse_iso(d: str):
    try:
        return datetime.fromisoformat(d)
    except Exception:
        return None


def _month_label(dt: datetime):
    return dt.strftime('%Y-%m')


def prepare_all(agg: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare Chart.js-compatible configs and raw aggregates.

    Returns a dict with keys matching what `overview.html` expects, e.g.
    {
      'monthly_spend': {...Chart.js config...},
      'cumulative_spend': {...},
      'tag_breakdown': {...},
      'payment_mode': {...},
      'created_history': {...},
      'upcoming_timeline': [...],
      'raw': {...}
    }
    """
    try:
        bills = agg.get('bills', []) or []
        # build monthly buckets by created_at
        start = _parse_iso(agg.get('start'))
        end = _parse_iso(agg.get('end'))
        months = []
        if start and end:
            cur = datetime(start.year, start.month, 1)
            while cur <= end:
                months.append(_month_label(cur))
                # increment month
                if cur.month == 12:
                    cur = datetime(cur.year + 1, 1, 1)
                else:
                    cur = datetime(cur.year, cur.month + 1, 1)

        monthly_totals = {m: 0.0 for m in months}
        monthly_counts = {m: 0 for m in months}
        for b in bills:
            ca = b.get('created_at')
            try:
                dt = datetime.fromisoformat(ca) if ca else None
            except Exception:
                dt = None
            label = _month_label(dt) if dt else None
            amt = (b.get('amount_cents', 0) or 0) / 100.0
            if label and label in monthly_totals:
                monthly_totals[label] += amt
                monthly_counts[label] += 1

        labels = months
        data = [monthly_totals.get(m, 0.0) for m in labels]
        counts = [monthly_counts.get(m, 0) for m in labels]

        # tag breakdown
        by_tag = agg.get('by_tag_cents', {}) or {}
        tag_labels = list(by_tag.keys())
        tag_values = [v / 100.0 for v in by_tag.values()]

        # payment modes breakdown from bills
        pm_map = {}
        for b in bills:
            pm = b.get('payment_mode') or 'other'
            pm_map.setdefault(pm, 0.0)
            pm_map[pm] += (b.get('amount_cents', 0) or 0) / 100.0
        pm_labels = list(pm_map.keys())
        pm_values = [pm_map[k] for k in pm_labels]

        # upcoming timeline: pick bills with next_due
        upcoming = []
        for b in bills:
            if b.get('next_due'):
                upcoming.append({
                    'id': b.get('id'),
                    'name': b.get('name'),
                    'due_date': b.get('next_due'),
                    'amount': (b.get('amount_cents', 0) or 0) / 100.0,
                    'tag': b.get('tag'),
                    'payment_mode': b.get('payment_mode')
                })
        upcoming = sorted(upcoming, key=lambda x: x.get('due_date') or '')[:12]

        raw = {
            'monthly': {'labels': labels, 'data': data, 'counts': counts},
            'by_tag_cents': by_tag,
            'payment_modes': pm_map,
            'top_bills': agg.get('top_bills', []),
            'total_cents': agg.get('total_cents', 0)
        }

        # Chart.js configs
        monthly_spend = {
            'type': 'line',
            'data': {
                'labels': labels,
                'datasets': [{
                    'label': 'Monthly spend',
                    'data': data,
                    'borderColor': '#2563EB',
                    'backgroundColor': 'rgba(37,99,235,0.08)',
                    'fill': True,
                }]
            },
            'options': {'responsive': True, 'maintainAspectRatio': False}
        }

        cumulative = []
        running = 0.0
        for v in data:
            running += v
            cumulative.append(running)
        cumulative_spend = {
            'type': 'line',
            'data': {
                'labels': labels,
                'datasets': [{
                    'label': 'Cumulative spend',
                    'data': cumulative,
                    'borderColor': '#16A34A',
                    'backgroundColor': 'rgba(22,163,74,0.08)',
                    'fill': True,
                }]
            },
            'options': {'responsive': True, 'maintainAspectRatio': False}
        }

        tag_breakdown = {
            'type': 'doughnut',
            'data': {'labels': tag_labels, 'datasets': [{'data': tag_values, 'backgroundColor': ['#60A5FA', '#34D399', '#FBBF24', '#F87171', '#A78BFA']}]},
            'options': {'responsive': True, 'maintainAspectRatio': False}
        }

        payment_mode = {
            'type': 'pie',
            'data': {'labels': pm_labels, 'datasets': [{'data': pm_values}]},
            'options': {'responsive': True, 'maintainAspectRatio': False}
        }

        created_history = {
            'type': 'bar',
            'data': {
                'labels': labels,
                'datasets': [{'label': 'Bills created', 'data': counts, 'backgroundColor': '#C084FC'}]
            },
            'options': {'responsive': True, 'maintainAspectRatio': False}
        }

        return {
            'monthly_spend': monthly_spend,
            'cumulative_spend': cumulative_spend,
            'tag_breakdown': tag_breakdown,
            'payment_mode': payment_mode,
            'created_history': created_history,
            'upcoming_timeline': upcoming,
            'raw': raw,
        }
    except Exception:
        return {'monthly_spend': None, 'cumulative_spend': None, 'tag_breakdown': None, 'payment_mode': None, 'created_history': None, 'upcoming_timeline': [], 'raw': {}}
