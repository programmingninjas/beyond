import asyncio
import math
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from pwdlib import PasswordHash
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine, or_
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./beyond.db')
SECRET = os.getenv('SECRET_KEY', 'local-development-change-me')
engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False} if DATABASE_URL.startswith('sqlite') else {})
SessionLocal = sessionmaker(engine, expire_on_commit=False)
passwords = PasswordHash.recommended()
bearer = HTTPBearer()

class Base(DeclarativeBase): pass
class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(100))
    bio: Mapped[str] = mapped_column(Text, default='')
    interests: Mapped[str] = mapped_column(Text, default='')
    profile_url: Mapped[str] = mapped_column(String(500), default='')
    enrichment_consent: Mapped[bool] = mapped_column(Boolean, default=False)
class Event(Base):
    __tablename__ = 'events'
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    title: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(Text, default='')
    category: Mapped[str] = mapped_column(String(80), default='Community')
    location: Mapped[str] = mapped_column(String(200), default='Online')
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    quiz: Mapped[dict] = mapped_column(JSON)
class Registration(Base):
    __tablename__ = 'registrations'
    __table_args__ = (UniqueConstraint('user_id', 'event_id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    event_id: Mapped[int] = mapped_column(ForeignKey('events.id'))
    personality: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
class Connection(Base):
    __tablename__ = 'connections'
    __table_args__ = (UniqueConstraint('low_id', 'high_id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    low_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    high_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    requester_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    accepted: Mapped[bool] = mapped_column(Boolean, default=False)
class Message(Base):
    __tablename__ = 'messages'
    id: Mapped[int] = mapped_column(primary_key=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    recipient_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

TEMPLATE = {'personalities': ['Explorer', 'Connector', 'Thinker'], 'questions': [
    {'question': 'What are you most excited to find at an event?', 'options': [{'text': 'Fresh ideas', 'personality': 'Explorer'}, {'text': 'New people', 'personality': 'Connector'}, {'text': 'Deeper insights', 'personality': 'Thinker'}]},
    {'question': 'How do you usually start a conversation?', 'options': [{'text': 'Ask about something unexpected', 'personality': 'Explorer'}, {'text': 'Introduce myself to the group', 'personality': 'Connector'}, {'text': 'Ask a thoughtful question', 'personality': 'Thinker'}]},
    {'question': 'What makes a gathering memorable?', 'options': [{'text': 'Discovering a new perspective', 'personality': 'Explorer'}, {'text': 'Making a meaningful connection', 'personality': 'Connector'}, {'text': 'Learning something useful', 'personality': 'Thinker'}]}]}

def db_session():
    with SessionLocal() as db: yield db

def now(): return datetime.now(timezone.utc)
def aware(dt): return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
def token_for(u): return jwt.encode({'sub': str(u.id), 'exp': now() + timedelta(days=7)}, SECRET, algorithm='HS256')
def get_user(token, db):
    try:
        payload = jwt.decode(token, SECRET, algorithms=['HS256']); user = db.get(User, int(payload['sub']))
        if user: return user
    except (jwt.PyJWTError, ValueError, KeyError): pass
    raise HTTPException(401, 'Invalid or expired session')
def current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(db_session)):
    return get_user(credentials.credentials, db)
def public_user(u): return {'id': u.id, 'name': u.name, 'bio': u.bio, 'interests': u.interests, 'profile_url': u.profile_url}
def event_data(e, db, user=None):
    reg = db.query(Registration).filter_by(event_id=e.id, user_id=user.id).first() if user else None
    owner = db.get(User, e.owner_id)
    return {'id': e.id, 'owner_id': e.owner_id, 'organizer': owner.name if owner else 'Organizer', 'title': e.title, 'description': e.description, 'category': e.category, 'location': e.location, 'starts_at': aware(e.starts_at).isoformat(), 'ends_at': aware(e.ends_at).isoformat(), 'published': e.published, 'registered': bool(reg), 'personality': reg.personality if reg else None, 'attendees': db.query(Registration).filter_by(event_id=e.id).count()}
def event_or_404(db, event_id):
    event = db.get(Event, event_id)
    if not event: raise HTTPException(404, 'Event not found')
    return event
def owner_event(db, event_id, user):
    event = event_or_404(db, event_id)
    if event.owner_id != user.id: raise HTTPException(403, 'Only the organizer can manage this event')
    return event
def registration(db, event_id, user_id): return db.query(Registration).filter_by(event_id=event_id, user_id=user_id).first()
def validate_quiz(q):
    if not isinstance(q, dict) or not isinstance(q.get('personalities'), list) or not isinstance(q.get('questions'), list): raise HTTPException(422, 'Quiz needs personalities and questions')
    types = q['personalities']
    if not types or len(types) > 20 or any(not isinstance(t, str) or not t.strip() or len(t) > 100 for t in types) or len(set(types)) != len(types): raise HTTPException(422, 'Personality names must be unique, nonempty strings')
    if not 1 <= len(q['questions']) <= 30: raise HTTPException(422, 'Quiz needs 1–30 questions')
    for question in q['questions']:
        if not isinstance(question, dict) or not isinstance(question.get('question'), str) or not question['question'].strip() or not isinstance(question.get('options'), list) or not 2 <= len(question['options']) <= 10: raise HTTPException(422, 'Each question needs text and 2–10 options')
        for option in question['options']:
            if not isinstance(option, dict) or not isinstance(option.get('text'), str) or not option['text'].strip() or option.get('personality') not in types: raise HTTPException(422, 'Each option needs text and a valid personality')
    return q

class AuthInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(default='', max_length=100)
class ProfileInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    bio: str = Field(default='', max_length=2000)
    interests: str = Field(default='', max_length=500)
    profile_url: str = Field(default='', max_length=500)
    enrichment_consent: bool = False
class EventInput(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    description: str = Field(default='', max_length=5000)
    category: str = Field(default='Community', max_length=80)
    location: str = Field(default='Online', max_length=200)
    starts_at: datetime
    ends_at: datetime
    published: bool = False
class QuizInput(BaseModel): quiz: dict[str, Any]
class AnswersInput(BaseModel): answers: list[int]
class TextInput(BaseModel): text: str = Field(min_length=1, max_length=2000)

app = FastAPI(title='Beyond API')
app.add_middleware(CORSMiddleware, allow_origins=[os.getenv('FRONTEND_ORIGIN', 'http://localhost:3000')], allow_origin_regex=r'http://(localhost|127\.0\.0\.1|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}):3000', allow_credentials=True, allow_methods=['*'], allow_headers=['*'])
# In-process invalidation bus. Payloads contain no private data; clients re-fetch
# through the normal authorized endpoints. Run one API worker (see README).
update_clients: set[WebSocket] = set()

@app.middleware('http')
async def publish_changes(request, call_next):
    response = await call_next(request)
    path = request.url.path
    # Invalidate event-wide caches on changes that can affect either side of a match.
    persona_match = re.fullmatch(r'/v2/events/(\d+)/persona', path)
    quiz_match = re.fullmatch(r'/events/(\d+)/quiz/submit', path)
    if response.status_code < 400 and ((request.method == 'PUT' and (path in ('/me', '/v2/profile') or persona_match)) or (request.method == 'POST' and quiz_match)):
        auth = request.headers.get('authorization', '')
        if auth.startswith('Bearer '):
            with SessionLocal() as db:
                try:
                    u = get_user(auth[7:], db)
                    event_ids = [int((persona_match or quiz_match).group(1))] if (persona_match or quiz_match) else [r.event_id for r in db.query(Registration).filter_by(user_id=u.id).all()]
                    for event_id in event_ids:
                        db.query(V2Recommendation).filter_by(event_id=event_id).delete()
                        if os.getenv('OPENAI_API_KEY'):
                            for reg in db.query(Registration).filter_by(event_id=event_id).filter(Registration.personality.is_not(None)).all():
                                active = db.query(V2Job).filter_by(kind='matching',event_id=event_id,user_id=reg.user_id,target_id=0).filter(V2Job.state.in_(['pending','running'])).first()
                                if not active: db.add(V2Job(kind='matching',event_id=event_id,user_id=reg.user_id,target_id=0,state='pending',error=''))
                    db.commit()
                except HTTPException: pass
    if response.status_code < 400 and request.method in ('POST', 'PUT', 'PATCH', 'DELETE') and (path == '/me' or path.startswith(('/events', '/connections', '/messages', '/v2/'))):
        for client in list(update_clients):
            try: await client.send_json({'type': 'changed'})
            except Exception: update_clients.discard(client)
    return response

@app.websocket('/ws/updates')
async def updates(ws: WebSocket, token: str):
    with SessionLocal() as db:
        try: get_user(token, db)
        except HTTPException: await ws.close(code=4401); return
    await ws.accept()
    update_clients.add(ws)
    try:
        while True:
            try: await asyncio.wait_for(ws.receive_text(), timeout=30)
            except asyncio.TimeoutError:
                with SessionLocal() as db:
                    try: get_user(token, db)
                    except HTTPException: await ws.close(code=4401); break
    except (WebSocketDisconnect, RuntimeError): pass
    finally: update_clients.discard(ws)

from v2 import install as install_v2
V2Profile, V2Persona, V2Block, V2Introduction = install_v2(app, Base, db_session, current_user, User, Event, Registration, Connection)

@app.on_event('startup')
def startup():
    from migrations import migrate
    migrate(engine, Base, ['v2_profiles', 'v2_personas', 'v2_blocks', 'v2_introductions'])
from networking import install as install_networking
V2Job, V2Recommendation, V2Transcript = install_networking(app, Base, SessionLocal, current_user, User, Event, Registration, Connection, V2Profile, V2Persona, V2Block, V2Introduction)
@app.get('/health')
def health(): return {'status': 'ok'}
@app.post('/auth/signup')
def signup(body: AuthInput, db: Session = Depends(db_session)):
    if not body.name.strip(): raise HTTPException(422, 'Name is required')
    email = body.email.lower()
    if db.query(User).filter_by(email=email).first(): raise HTTPException(409, 'Email already registered')
    u = User(email=email, password=passwords.hash(body.password), name=body.name.strip()); db.add(u); db.commit(); db.refresh(u)
    return {'token': token_for(u), 'user': public_user(u)}
@app.post('/auth/login')
def login(body: AuthInput, db: Session = Depends(db_session)):
    u = db.query(User).filter_by(email=body.email.lower()).first()
    if not u or not passwords.verify(body.password, u.password): raise HTTPException(401, 'Invalid email or password')
    return {'token': token_for(u), 'user': public_user(u)}
@app.get('/me')
def me(user: User = Depends(current_user)): return {**public_user(user), 'email': user.email, 'enrichment_consent': user.enrichment_consent}
@app.put('/me')
def update_me(body: ProfileInput, user: User = Depends(current_user), db: Session = Depends(db_session)):
    for k, v in body.model_dump().items(): setattr(user, k, v)
    db.commit(); return public_user(user)
@app.get('/quiz-templates')
def templates(user: User = Depends(current_user)): return [{'id': 'conversation-starters', 'name': 'Conversation starters', 'description': 'A placeholder quiz to get your community talking.', 'quiz': TEMPLATE}]
@app.get('/events')
def events(user: User = Depends(current_user), db: Session = Depends(db_session)):
    return [event_data(e, db, user) for e in db.query(Event).filter(or_(Event.published == True, Event.owner_id == user.id)).order_by(Event.starts_at).all()]
@app.post('/events')
def create_event(body: EventInput, user: User = Depends(current_user), db: Session = Depends(db_session)):
    if not body.starts_at.tzinfo or not body.ends_at.tzinfo or body.ends_at <= body.starts_at: raise HTTPException(422, 'Provide timezone-aware start and end times, with end after start')
    e = Event(**body.model_dump(), owner_id=user.id, quiz=TEMPLATE); db.add(e); db.commit(); db.refresh(e); return event_data(e, db, user)
@app.get('/events/{event_id}')
def get_event(event_id: int, user: User = Depends(current_user), db: Session = Depends(db_session)):
    e = event_or_404(db, event_id)
    if not e.published and e.owner_id != user.id: raise HTTPException(404, 'Event not found')
    return event_data(e, db, user)
@app.put('/events/{event_id}')
def update_event(event_id: int, body: EventInput, user: User = Depends(current_user), db: Session = Depends(db_session)):
    e = owner_event(db, event_id, user)
    if not body.starts_at.tzinfo or not body.ends_at.tzinfo or body.ends_at <= body.starts_at: raise HTTPException(422, 'Provide timezone-aware start and end times, with end after start')
    for k, v in body.model_dump().items(): setattr(e, k, v)
    db.commit(); return event_data(e, db, user)
@app.delete('/events/{event_id}')
def delete_event(event_id: int, user: User = Depends(current_user), db: Session = Depends(db_session)):
    e = owner_event(db, event_id, user); db.query(V2Transcript).filter(V2Transcript.introduction_id.in_(db.query(V2Introduction.id).filter_by(event_id=e.id))).delete(synchronize_session=False); db.query(V2Job).filter_by(event_id=e.id).delete(); db.query(V2Recommendation).filter_by(event_id=e.id).delete(); db.query(V2Introduction).filter_by(event_id=e.id).delete(); db.query(V2Persona).filter_by(event_id=e.id).delete(); db.query(Registration).filter_by(event_id=e.id).delete(); db.delete(e); db.commit(); return {'ok': True}
@app.post('/events/{event_id}/register')
def register(event_id: int, user: User = Depends(current_user), db: Session = Depends(db_session)):
    e = event_or_404(db, event_id)
    if not e.published or aware(e.starts_at) <= now(): raise HTTPException(400, 'Registration is closed')
    if not registration(db, event_id, user.id): db.add(Registration(event_id=event_id, user_id=user.id)); db.commit()
    return event_data(e, db, user)
@app.get('/events/{event_id}/quiz')
def get_quiz(event_id: int, user: User = Depends(current_user), db: Session = Depends(db_session)):
    e = event_or_404(db, event_id)
    if e.owner_id == user.id: return e.quiz
    if not e.published or not registration(db, event_id, user.id): raise HTTPException(403, 'Register first')
    return {'questions': [{'question': q['question'], 'options': [o['text'] for o in q['options']]} for q in e.quiz['questions']]}
@app.put('/events/{event_id}/quiz')
def update_quiz(event_id: int, body: QuizInput, user: User = Depends(current_user), db: Session = Depends(db_session)):
    e = owner_event(db, event_id, user)
    if db.query(Registration).filter(Registration.event_id == event_id, Registration.personality.is_not(None)).first(): raise HTTPException(409, 'Quiz cannot be changed after a participant completes it')
    e.quiz = validate_quiz(body.quiz); db.commit(); return e.quiz
@app.post('/events/{event_id}/quiz/submit')
def submit_quiz(event_id: int, body: AnswersInput, user: User = Depends(current_user), db: Session = Depends(db_session)):
    e = event_or_404(db, event_id); reg = registration(db, event_id, user.id)
    if not e.published or not reg: raise HTTPException(403, 'Register first')
    if aware(e.starts_at) <= now(): raise HTTPException(400, 'Quiz is closed')
    if reg.personality: raise HTTPException(409, 'Quiz already completed')
    questions = e.quiz['questions']
    if len(body.answers) != len(questions) or any(i < 0 or i >= len(q['options']) for i, q in zip(body.answers, questions)): raise HTTPException(422, 'Answer every question with a valid option')
    scores = {p: 0 for p in e.quiz['personalities']}
    for i, q in zip(body.answers, questions): scores[q['options'][i]['personality']] += 1
    reg.personality = max(scores, key=scores.get); db.commit(); return {'personality': reg.personality}
@app.get('/events/{event_id}/recommendations')
def recommendations(event_id: int, user: User = Depends(current_user), db: Session = Depends(db_session)):
    e = event_or_404(db, event_id); own = registration(db, event_id, user.id)
    if not e.published or not own or not own.personality: raise HTTPException(403, 'Complete the quiz first')
    interests = {x.strip().lower() for x in user.interests.split(',') if x.strip()}
    rows = []
    for r in db.query(Registration).filter(Registration.event_id == event_id, Registration.user_id != user.id, Registration.personality.is_not(None)).all():
        profile = db.get(V2Profile, r.user_id)
        if (profile and not profile.discoverable) or db.query(V2Block).filter(or_((V2Block.user_id == user.id) & (V2Block.other_id == r.user_id), (V2Block.user_id == r.user_id) & (V2Block.other_id == user.id))).first(): continue
        other = db.get(User, r.user_id); shared = sorted(interests & {x.strip().lower() for x in other.interests.split(',') if x.strip()})
        rows.append({**public_user(other), 'personality': r.personality, 'shared_interests': shared, 'same_personality': r.personality == own.personality})
    return sorted(rows, key=lambda x: (not x['same_personality'], -len(x['shared_interests']), x['name'].lower()))
@app.get('/connections')
def connections(user: User = Depends(current_user), db: Session = Depends(db_session)):
    result = []
    for c in db.query(Connection).filter(or_(Connection.low_id == user.id, Connection.high_id == user.id)).all():
        other = db.get(User, c.high_id if c.low_id == user.id else c.low_id)
        result.append({'id': c.id, 'user': public_user(other), 'accepted': c.accepted, 'incoming': c.requester_id != user.id})
    return result
@app.post('/connections/{other_id}')
def connect(other_id: int, user: User = Depends(current_user), db: Session = Depends(db_session)):
    if other_id == user.id or not db.get(User, other_id): raise HTTPException(400, 'Invalid participant')
    if db.query(V2Block).filter(or_((V2Block.user_id == user.id) & (V2Block.other_id == other_id), (V2Block.user_id == other_id) & (V2Block.other_id == user.id))).first(): raise HTTPException(403, 'Participant unavailable')
    low, high = sorted([user.id, other_id]); c = db.query(Connection).filter_by(low_id=low, high_id=high).first()
    if c: raise HTTPException(409, 'Connection already exists')
    c = Connection(low_id=low, high_id=high, requester_id=user.id); db.add(c); db.commit(); return {'id': c.id}
@app.post('/connections/{connection_id}/accept')
def accept(connection_id: int, user: User = Depends(current_user), db: Session = Depends(db_session)):
    c = db.get(Connection, connection_id)
    if not c or user.id not in (c.low_id, c.high_id) or c.requester_id == user.id: raise HTTPException(403, 'Cannot accept this request')
    c.accepted = True; db.commit(); return {'ok': True}
def require_connection(db, user_id, other_id):
    if db.query(V2Block).filter(or_((V2Block.user_id == user_id) & (V2Block.other_id == other_id), (V2Block.user_id == other_id) & (V2Block.other_id == user_id))).first(): raise HTTPException(403, 'Participant unavailable')
    low, high = sorted([user_id, other_id]); c = db.query(Connection).filter_by(low_id=low, high_id=high, accepted=True).first()
    if not c: raise HTTPException(403, 'An accepted connection is required')
@app.get('/messages/{other_id}')
def messages(other_id: int, user: User = Depends(current_user), db: Session = Depends(db_session)):
    require_connection(db, user.id, other_id)
    rows = db.query(Message).filter(or_((Message.sender_id == user.id) & (Message.recipient_id == other_id), (Message.sender_id == other_id) & (Message.recipient_id == user.id))).order_by(Message.created_at).all()
    return [{'id': m.id, 'sender_id': m.sender_id, 'text': m.text, 'created_at': aware(m.created_at).isoformat()} for m in rows]
@app.post('/messages/{other_id}')
def send_message(other_id: int, body: TextInput, user: User = Depends(current_user), db: Session = Depends(db_session)):
    require_connection(db, user.id, other_id); text = body.text.strip()
    if not text: raise HTTPException(422, 'Message cannot be empty')
    db.add(Message(sender_id=user.id, recipient_id=other_id, text=text)); db.commit(); return {'ok': True}

# A provider must only be called after checking the participant's explicit consent.
class ProfileEnrichmentProvider:
    async def enrich(self, profile_url: str) -> dict[str, Any]:
        raise NotImplementedError('Configure an enrichment provider in a future release')

rooms: dict[int, dict[WebSocket, dict]] = {}
async def broadcast(event_id, payload):
    for ws in list(rooms.get(event_id, {})):
        try: await ws.send_json(payload)
        except Exception: rooms[event_id].pop(ws, None)
async def room_snapshot(event_id):
    members = rooms.get(event_id, {})
    with SessionLocal() as db:
        hidden = {(b.user_id,b.other_id) for b in db.query(V2Block).all()}
    for peer, person in list(members.items()):
        visible = [p for p in members.values() if p['room_id'] == person['room_id'] and (p['id'],person['id']) not in hidden and (person['id'],p['id']) not in hidden]
        try: await peer.send_json({'type': 'presence', 'participants': visible})
        except Exception: members.pop(peer, None)
def room_access(event_id, user_id):
    with SessionLocal() as db:
        event = db.get(Event, event_id)
        eligible = registration(db, event_id, user_id)
        if not event or not event.published or not eligible or not eligible.personality:
            return None
        return aware(event.starts_at)

@app.websocket('/ws/events/{event_id}')
async def room(ws: WebSocket, event_id: int, token: str):
    with SessionLocal() as db:
        try: user = get_user(token, db)
        except HTTPException: await ws.close(code=4401); return
        e = db.get(Event, event_id); reg = registration(db, event_id, user.id)
        if not e or not e.published or not reg or not reg.personality or aware(e.starts_at) <= now(): await ws.close(code=4403); return
        deadline = aware(e.starts_at)
        slot = len(rooms.get(event_id, {}))
        person = {**public_user(user), 'personality': reg.personality, 'x': 15 + (slot % 5) * 17, 'y': 25 + (slot // 5 % 4) * 16, 'direction': 'down', 'walking': False, 'room_id': 'plaza'}
    await ws.accept(); rooms.setdefault(event_id, {})[ws] = person; await room_snapshot(event_id)
    try:
        next_access_check = asyncio.get_running_loop().time() + 5
        while True:
            clock = asyncio.get_running_loop().time()
            if clock >= next_access_check:
                deadline = await asyncio.to_thread(room_access, event_id, person['id'])
                if deadline is None:
                    await ws.close(code=4403); break
                next_access_check = asyncio.get_running_loop().time() + 5
            remaining = (deadline - now()).total_seconds()
            if remaining <= 0: await ws.close(code=4403); break
            try: data = await asyncio.wait_for(ws.receive_json(), timeout=min(remaining, max(0.01, next_access_check - clock)))
            except asyncio.TimeoutError: continue
            if data.get('type') == 'room':
                if data.get('room_id') in ('plaza','cafe','garden','arcade','lab'):
                    person['room_id'] = data['room_id']; person['x'] = 50; person['y'] = 50
                    await ws.send_json({'type':'room_changed','room_id':person['room_id'],'x':50,'y':50})
                    await room_snapshot(event_id)
            elif data.get('type') == 'move':
                try:
                    x, y = float(data['x']), float(data['y'])
                    if not math.isfinite(x) or not math.isfinite(y): continue
                    person['x'], person['y'] = max(5, min(95, x)), max(10, min(90, y))
                    person['direction'] = data.get('direction') if data.get('direction') in ('up', 'down', 'left', 'right') else 'down'
                    person['walking'] = data.get('walking') is True
                except (ValueError, TypeError, KeyError): continue
                await room_snapshot(event_id)
            elif data.get('type') == 'chat':
                text = str(data.get('text', '')).strip()[:500]
                target_id = data.get('target_id')
                targets = [(peer, other) for peer, other in rooms.get(event_id, {}).items()
                           if other['id'] == target_id and other['id'] != person['id'] and other['room_id'] == person['room_id']
                           and math.hypot(other['x'] - person['x'], other['y'] - person['y']) <= 18]
                if text and targets:
                    with SessionLocal() as db:
                        if db.query(V2Block).filter(or_((V2Block.user_id == person['id']) & (V2Block.other_id == target_id), (V2Block.user_id == target_id) & (V2Block.other_id == person['id']))).first():
                            await ws.send_json({'type':'chat_error','message':'Participant unavailable.'}); continue
                    payload = {'type': 'chat', 'user': person['name'], 'user_id': person['id'], 'target_id': target_id, 'text': text}
                    await ws.send_json(payload)
                    for peer, _ in targets:
                        try: await peer.send_json(payload)
                        except Exception: pass
                elif text:
                    await ws.send_json({'type': 'chat_error', 'message': 'Move closer to this person to talk.'})
    except (WebSocketDisconnect, RuntimeError): pass
    finally:
        rooms.get(event_id, {}).pop(ws, None); await room_snapshot(event_id)
