import os
import json
import hashlib
from datetime import datetime, timedelta

from db import db
from models import Bill, User, AgentResult


def _make_cache_key(user_id, message, context_obj):
    h = hashlib.sha256()
    key_material = f"{user_id}|{message}|{json.dumps(context_obj, sort_keys=True, default=str)}"
    h.update(key_material.encode('utf-8'))
    return h.hexdigest()


def _load_from_cache(cache_key, user_id, ttl_seconds: int):
    agent_key = f"chat_agent_v1:{cache_key}"
    row = AgentResult.query.filter_by(agent_key=agent_key, user_id=user_id).order_by(AgentResult.created_at.desc()).first()
    if not row:
        return None
    try:
        payload = json.loads(row.payload)
    except Exception:
        return None
    created = row.created_at
    if ttl_seconds > 0 and (datetime.utcnow() - created) > timedelta(seconds=ttl_seconds):
        return None
    return payload


def _save_to_cache(cache_key, user_id, payload_obj):
    agent_key = f"chat_agent_v1:{cache_key}"
    row = AgentResult(agent_key=agent_key, user_id=user_id, payload=json.dumps(payload_obj, default=str))
    db.session.add(row)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()


def generate_chat_response(user_id: str | None, message: str, use_cache: bool = True) -> dict:
    """Generate a chat response for a specific user. Returns a dict {text, model, cached}.

    Caching: uses `AgentResult` rows with agent_key `chat_agent_v1:<cache_key>`. TTL controlled by env CHAT_CACHE_TTL_SECONDS (default 300s)."""
    # build context
    context = {}
    try:
        if user_id:
            bills = Bill.query.filter_by(user_id=user_id).order_by(Bill.created_at.desc()).limit(200).all()
            bill_dicts = [b.to_dict() for b in bills]
            total_cents = sum((b.amount_cents or 0) for b in bills)
            monthly_estimate = 0
            for b in bills:
                if b.period == 'monthly' or b.period is None:
                    monthly_estimate += (b.amount_cents or 0)
                elif b.period == 'yearly':
                    monthly_estimate += (b.amount_cents or 0) / 12.0
            context = {
                'user': {'id': user_id},
                'bills': bill_dicts,
                'total_amount_cents': int(total_cents),
                'monthly_estimate_cents': int(monthly_estimate),
            }
    except Exception:
        context = {}

    cache_ttl = int(os.environ.get('CHAT_CACHE_TTL_SECONDS') or os.environ.get('CHAT_CACHE_TTL') or 300)
    cache_key = _make_cache_key(user_id or 'anon', message, context)

    if use_cache:
        cached = _load_from_cache(cache_key, user_id or 'anon', cache_ttl)
        if cached:
            cached['cached'] = True
            return cached

    # call Gemini via google.genai
    from google import genai
    # Prefer explicit API key to avoid ambiguous client initialization errors
    api_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_GENAI_API_KEY') or os.environ.get('GENAI_API_KEY')
    if not api_key:
        raise RuntimeError('GEMINI_API_KEY is not set in environment. Set GEMINI_API_KEY in .env or environment before calling the chat agent.')
    client = genai.Client(api_key=api_key)
    model = os.environ.get('GEMINI_MODEL') or os.environ.get('GEMINI_MODEL_NAME') or 'gemini-2.5-flash'

    system_instructions = (
        "You are BillBot's assistant. Use only the provided 'context' JSON to answer the user's questions about their bills, spendings, and related data. "
        "You MAY analyze the data and provide budget recommendations or insights that can be reasonably derived from the context (for example, summaries, trend observations, and budgeting suggestions based on spending patterns). "
        "Do not invent facts that are not inferable from the context. If required details are missing, state that and ask for clarification. Reply in Markdown."
    )
    contents = system_instructions + "\n\nContext JSON:\n" + json.dumps(context, default=str) + "\n\nUser question:\n" + message + "\n\nAnswer in Markdown."

    try:
        response = client.models.generate_content(model=model, contents=contents)
    except Exception as e:
        # surface provider errors with context
        raise RuntimeError(f'GenAI provider error: {e}') from e
    text = getattr(response, 'text', None) or str(response)
    out = {'text': text, 'model': model, 'cached': False}

    # persist to cache
    try:
        _save_to_cache(cache_key, user_id or 'anon', out)
    except Exception:
        pass

    return out
