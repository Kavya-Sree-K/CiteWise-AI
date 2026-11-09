"""Stored chats: every question and answer is saved, per user."""
import json
from datetime import datetime

from app.models import Conversation, Message
from app.safety import redact

KEEP_FOR_CONTEXT = 3        # earlier questions the router/retriever may use for follow-ups


def get_or_create(db, user, conversation_id, first_question):
    """Return the user's conversation. None if it does not exist or belongs to someone else."""
    if conversation_id:
        conv = db.get(Conversation, conversation_id)
        if not conv or conv.username != user.username:
            return None
        return conv
    title = redact(first_question).strip().replace("\n", " ")[:60] or "New chat"
    conv = Conversation(username=user.username, title=title)
    db.add(conv)
    db.commit()
    return conv


def recent_questions(db, conversation_id):
    """The user's last questions in this chat (already redacted), oldest first."""
    rows = (db.query(Message)
              .filter(Message.conversation_id == conversation_id, Message.role == "user")
              .order_by(Message.id.desc()).limit(KEEP_FOR_CONTEXT).all())
    return [m.content[:500] for m in reversed(rows)]


def add_turn(db, conv, question, out):
    """Save the question and the answer. The question is stored with personal data removed."""
    payload = {k: out.get(k) for k in ("status", "sources", "steps", "details", "procedure",
                                       "comparison", "follow_ups", "input_tokens",
                                       "output_tokens", "cost_usd")}
    db.add(Message(conversation_id=conv.id, role="user", content=redact(question)))
    db.add(Message(conversation_id=conv.id, role="assistant", content=out["answer"],
                   run_id=out.get("run_id"), payload=json.dumps(payload)))
    conv.updated_at = datetime.utcnow()
    db.commit()


def message_view(m):
    data = {"role": m.role, "text": m.content, "run_id": m.run_id, "time": str(m.created_at)}
    if m.role == "assistant" and m.payload:
        data.update(json.loads(m.payload))
    return data