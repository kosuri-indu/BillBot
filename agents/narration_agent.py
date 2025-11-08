import os
import json
from typing import Dict, Any
try:
    from google import genai
except Exception:
    genai = None

def _simple_rule_narration(agg: Dict[str, Any]) -> str:
    labels = agg['monthly']['labels']
    data = agg['monthly']['data']
    if not labels or not data:
        return 'No history yet. Add your first bill to see insights.'
    last = data[-1]
    prev = data[-2] if len(data) > 1 else 0
    pct = (last - prev) / prev * 100 if prev else None
    top_tag = None
    if agg['tag_breakdown']['labels']:
        max_idx = agg['tag_breakdown']['data'].index(max(agg['tag_breakdown']['data']))
        top_tag = agg['tag_breakdown']['labels'][max_idx]
    parts = [f'Your most recent month spending: ₹{last:.2f}.']
    if pct is not None:
        parts.append(f'This is {pct:+.1f}% vs previous month.')
    if top_tag:
        parts.append(f'Biggest category: {top_tag}.')
    return ' '.join(parts)

def generate_narration(agg: Dict[str, Any], user_id: str=None) -> Dict[str, Any]:
    safe_payload = {'monthly_labels': agg['monthly']['labels'][-6:], 'monthly_values': agg['monthly']['data'][-6:], 'top_tags': agg['tag_breakdown']['labels'][:5], 'top_tag_values': agg['tag_breakdown']['data'][:5]}
    bullets = []
    if agg.get('tag_breakdown') and agg['tag_breakdown']['labels']:
        top_tags = list(zip(agg['tag_breakdown']['labels'], agg['tag_breakdown']['data']))[:3]
        bullets.append('Top categories: ' + ', '.join([f'{t[0]} (₹{t[1]:.2f})' for t in top_tags]))
    labels = agg['monthly']['labels']
    data = agg['monthly']['data']
    if len(data) >= 2:
        last = data[-1]
        prev = data[-2]
        pct = (last - prev) / prev * 100 if prev else None
        if pct is not None:
            bullets.append(f'Month-over-month change: {pct:+.1f}%')
    top_changes = []
    if len(data) >= 3:
        changes = [(labels[i], data[i] - (data[i - 1] if i > 0 else 0)) for i in range(1, len(data))]
        inc = max(changes, key=lambda x: x[1])
        top_changes.append({'month': inc[0], 'delta': round(inc[1], 2)})
    if genai is not None and os.environ.get('GEMINI_API_KEY'):
        try:
            client = genai.Client()
            prompt = f"You are a helpful assistant that summarizes financial metrics.\nHere is aggregated data (last 6 months labels): {safe_payload['monthly_labels']}\nHere are totals: {safe_payload['monthly_values']}\nTop tags: {safe_payload['top_tags']} with values {safe_payload['top_tag_values']}\nProvide a short (1-2 sentence) human-friendly insight about recent spending trends. Be concise and avoid guessing beyond given numbers."
            response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
            text = getattr(response, 'text', None) or str(response)
            result = {'summary': text.strip(), 'model': 'gemini-2.5-flash'}
        except Exception:
            result = {'summary': _simple_rule_narration(agg), 'model': 'fallback'}
    else:
        result = {'summary': _simple_rule_narration(agg), 'model': 'fallback'}
    result['bullets'] = bullets
    result['top_changes'] = top_changes
    return result
if __name__ == '__main__':
    print('Use generate_narration(agg, user_id) to get a JSON-ready narration')
