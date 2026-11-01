import asyncio
from collections import deque
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
from world import CHAT_RADIUS, REVISION, ROOMS, RADIUS, WALK_SPEED, blocked, in_bounds, public_worlds, safe_spawn, shape_contains, swept_move

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
class EventFields(Base):
    __tablename__ = 'event_registration_fields'
    event_id: Mapped[int] = mapped_column(ForeignKey('events.id'), primary_key=True)
    fields: Mapped[list] = mapped_column(JSON, default=list)
class RegistrationAnswers(Base):
    __tablename__ = 'event_registration_answers'
    registration_id: Mapped[int] = mapped_column(ForeignKey('registrations.id'), primary_key=True)
    answers: Mapped[dict] = mapped_column(JSON, default=dict)
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

PERSONALITIES = ['Adventurer', 'Innovator', 'Mystic', 'Synergist']
TEMPLATE = {'personalities': PERSONALITIES, 'questions': [
    {'question': 'At a party, you tend to:', 'options': [{'text': 'Mingle with a large group.'}, {'text': 'Find a small group to have a deep conversation with.'}, {'text': 'Observe the party from the sidelines.'}, {'text': 'Take center stage and entertain everyone.'}]},
    {'question': 'When making a decision, you:', 'options': [{'text': 'Weigh the pros and cons carefully.'}, {'text': 'Trust your gut feeling and intuition.'}, {'text': 'Seek advice from others.'}, {'text': 'Like to have all the information before making a choice.'}]},
    {'question': 'Your ideal Saturday morning involves:', 'options': [{'text': 'A bustling activity with friends or family.'}, {'text': 'Learning a new skill or tackling a creative project.'}, {'text': 'Quiet relaxation and reflection.'}, {'text': 'A spontaneous adventure or trying something new.'}]},
    {'question': 'You would describe yourself as:', 'options': [{'text': 'Outgoing and sociable.'}, {'text': 'Curious and imaginative.'}, {'text': 'Reserved and introspective.'}, {'text': 'Energetic and enthusiastic.'}]},
    {'question': 'In a disagreement, you prefer to:', 'options': [{'text': 'Debate the issue and find a common ground.'}, {'text': 'Offer a creative solution that satisfies everyone.'}, {'text': 'Avoid conflict altogether.'}, {'text': 'Assert your position and win the argument.'}]},
    {'question': 'What motivates you the most?', 'options': [{'text': 'Recognition and praise from others.'}, {'text': 'Learning and personal growth.'}, {'text': 'Inner peace and harmony.'}, {'text': 'New experiences and challenges.'}]},
    {'question': 'You get lost in a book that is:', 'options': [{'text': 'A thrilling adventure story.'}, {'text': 'A thought-provoking exploration of ideas.'}, {'text': 'A heartwarming and emotional story.'}, {'text': 'A funny and lighthearted read.'}]},
]}
for question in TEMPLATE['questions']:
    for index, option in enumerate(question['options']):
        option['personality'] = PERSONALITIES[index]

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
    return {'id': e.id, 'owner_id': e.owner_id, 'organizer': owner.name if owner else 'Organizer', 'title': e.title, 'description': e.description, 'category': e.category, 'location': e.location, 'starts_at': aware(e.starts_at).isoformat(), 'ends_at': aware(e.ends_at).isoformat(), 'published': e.published, 'registered': bool(reg), 'attendees': db.query(Registration).filter_by(event_id=e.id).count()}
def event_or_404(db, event_id):
    event = db.get(Event, event_id)
    if not event: raise HTTPException(404, 'Event not found')
    return event
def owner_event(db, event_id, user):
    event = event_or_404(db, event_id)
    if event.owner_id != user.id: raise HTTPException(403, 'Only the organizer can manage this event')
    return event
def registration(db, event_id, user_id): return db.query(Registration).filter_by(event_id=event_id, user_id=user_id).first()
class AuthInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(default='', max_length=100)
class ProfileInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    bio: str = Field(default='', max_length=1000)
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
class ExtraField(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    required: bool = False
class ExtraFieldsInput(BaseModel): fields: list[ExtraField] = Field(max_length=20)
class RegistrationInput(BaseModel): answers: dict[str, str] = Field(default_factory=dict)
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
    if response.status_code < 400 and ((request.method == 'PUT' and (path in ('/me', '/v2/profile') or persona_match)) or (request.method == 'POST' and (path in ('/profile/personality-quiz', '/v2/profile/enrichment/apply') or re.fullmatch(r'/events/\d+/register',path)))):
        auth = request.headers.get('authorization', '')
        if auth.startswith('Bearer '):
            with SessionLocal() as db:
                try:
                    u = get_user(auth[7:], db)
                    event_ids = [int(persona_match.group(1))] if persona_match else [r.event_id for r in db.query(Registration).filter_by(user_id=u.id).all()]
                    for event_id in event_ids:
                        db.query(V2Recommendation).filter_by(event_id=event_id).delete()
                        if os.getenv('OPENAI_API_KEY'):
                            for reg in db.query(Registration).filter_by(event_id=event_id).all():
                                # Keep a follow-up queued when a profile changes
                                # during an in-flight match. That run may reject
                                # its stale snapshot, so it cannot cover this edit.
                                pending = db.query(V2Job).filter_by(kind='matching',event_id=event_id,user_id=reg.user_id,target_id=0,state='pending').first()
                                if not pending: db.add(V2Job(kind='matching',event_id=event_id,user_id=reg.user_id,target_id=0,state='pending',error=''))
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
from enrichment_routes import install as install_enrichment
install_enrichment(app, db_session, current_user, User, V2Profile, SECRET)

@app.on_event('startup')
def startup():
    from migrations import migrate
    migrate(engine, Base, ['v2_profiles', 'v2_personas', 'v2_blocks', 'v2_introductions'])
from networking import install as install_networking
V2Job, V2Recommendation, V2Transcript = install_networking(app, Base, SessionLocal, current_user, User, Event, Registration, Connection, V2Profile, V2Persona, V2Block, V2Introduction)
@app.get('/health')
def health(): return {'status': 'ok'}
@app.get('/worlds')
def get_worlds(): return public_worlds()
@app.get('/worlds/{room_id}')
def get_world(room_id: str):
    if room_id not in ROOMS: raise HTTPException(404, 'World not found')
    return {'revision': REVISION, 'coordinateSystem': public_worlds()['coordinateSystem'], 'room': ROOMS[room_id]}
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
    row = db.get(V2Profile, user.id)
    if row:
        data = dict(row.data or {}); sources = dict(data.get('enrichment_sources') or {})
        for key in ('bio', 'interests'):
            if getattr(user, key) != getattr(body, key): sources.pop(key, None)
        data['enrichment_sources'] = sources; row.data = data
    for k, v in body.model_dump().items(): setattr(user, k, v)
    db.commit(); return public_user(user)
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
    e = owner_event(db, event_id, user); db.query(V2Transcript).filter(V2Transcript.introduction_id.in_(db.query(V2Introduction.id).filter_by(event_id=e.id))).delete(synchronize_session=False); db.query(V2Job).filter_by(event_id=e.id).delete(); db.query(V2Recommendation).filter_by(event_id=e.id).delete(); db.query(V2Introduction).filter_by(event_id=e.id).delete(); db.query(V2Persona).filter_by(event_id=e.id).delete(); db.query(RegistrationAnswers).filter(RegistrationAnswers.registration_id.in_(db.query(Registration.id).filter_by(event_id=e.id))).delete(synchronize_session=False); db.query(EventFields).filter_by(event_id=e.id).delete(); db.query(Registration).filter_by(event_id=e.id).delete(); db.delete(e); db.commit(); return {'ok': True}
@app.get('/profile/personality-quiz')
def profile_quiz(user: User = Depends(current_user)):
    return {'personalities': PERSONALITIES, 'questions': [{'question': q['question'], 'options': [o['text'] for o in q['options']]} for q in TEMPLATE['questions']]}
@app.post('/profile/personality-quiz')
def profile_quiz_submit(body: AnswersInput, user: User = Depends(current_user), db: Session = Depends(db_session)):
    questions = TEMPLATE['questions']
    if len(body.answers) != len(questions) or any(i < 0 or i >= len(q['options']) for i,q in zip(body.answers, questions)):
        raise HTTPException(422, 'Answer every question')
    scores = {p: 0 for p in TEMPLATE['personalities']}
    for i,q in zip(body.answers,questions): scores[q['options'][i]['personality']] += 1
    result = max(scores, key=scores.get)
    row = db.get(V2Profile,user.id)
    if not row: row=V2Profile(user_id=user.id,data={},discoverable=True); db.add(row)
    row.data = {**(row.data or {}), 'personality_result':result}; db.commit()
    descriptions = {
        'Adventurer': 'Fearless and spontaneous, you bring energy to new experiences and make every gathering an opportunity to explore.',
        'Innovator': 'Curious and imaginative, you thrive on ideas, creative possibilities, and learning something new.',
        'Mystic': 'Calm and insightful, you value reflection, inner harmony, and meaningful moments.',
        'Synergist': 'Warm and engaging, you light up a room and help people feel connected.',
    }
    return {'personality':result, 'scores':scores, 'description':descriptions[result]}
@app.get('/events/{event_id}/registration-fields')
def registration_fields(event_id: int, user: User = Depends(current_user), db: Session = Depends(db_session)):
    e = event_or_404(db,event_id)
    if not e.published and e.owner_id != user.id: raise HTTPException(404, 'Event not found')
    row=db.get(EventFields,event_id)
    return {'fields': row.fields if row else []}
@app.put('/events/{event_id}/registration-fields')
def update_registration_fields(event_id: int, body: ExtraFieldsInput, user: User = Depends(current_user), db: Session = Depends(db_session)):
    owner_event(db,event_id,user)
    if db.query(Registration).filter_by(event_id=event_id).first(): raise HTTPException(409, 'Registration fields cannot change after someone registers')
    labels = [f.label.strip() for f in body.fields]
    if any(not label for label in labels) or len(set(label.casefold() for label in labels)) != len(labels): raise HTTPException(422, 'Field labels must be nonempty and unique')
    row=db.get(EventFields,event_id)
    if not row: row=EventFields(event_id=event_id,fields=[]); db.add(row)
    row.fields=[{'label':label,'required':f.required} for label,f in zip(labels,body.fields)]; db.commit()
    return {'fields':row.fields}
@app.post('/events/{event_id}/register')
def register(event_id: int, body: RegistrationInput = RegistrationInput(), user: User = Depends(current_user), db: Session = Depends(db_session)):
    from profile_rules import completion
    e = event_or_404(db, event_id)
    if not e.published or aware(e.starts_at) <= now(): raise HTTPException(400, 'Registration is closed')
    existing=registration(db,event_id,user.id)
    if existing: return event_data(e,db,user)
    p=db.get(V2Profile,user.id); progress=completion(user,p.data if p else {})
    if not progress['basic_complete']: raise HTTPException(403, 'Complete your basic profile before registering: ' + ', '.join(progress['missing_basic']))
    fields=db.get(EventFields,event_id); fields=fields.fields if fields else []
    labels={f['label'] for f in fields}
    if set(body.answers)-labels: raise HTTPException(422, 'Unknown registration fields')
    if any(f['required'] and not body.answers.get(f['label'],'').strip() for f in fields): raise HTTPException(422, 'Complete all required registration fields')
    if any(len(v)>2000 for v in body.answers.values()): raise HTTPException(422, 'Registration answers must be at most 2000 characters')
    reg=Registration(event_id=event_id,user_id=user.id); db.add(reg); db.flush()
    db.add(RegistrationAnswers(registration_id=reg.id,answers=body.answers)); db.commit()
    return event_data(e,db,user)
@app.get('/events/{event_id}/registration-answers')
def registration_answers(event_id: int, user: User = Depends(current_user), db: Session = Depends(db_session)):
    owner_event(db,event_id,user)
    rows=db.query(Registration).filter_by(event_id=event_id).all()
    return [{'user_id':r.user_id,'name':db.get(User,r.user_id).name,'answers':(db.get(RegistrationAnswers,r.id).answers if db.get(RegistrationAnswers,r.id) else {})} for r in rows]
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

rooms: dict[int, dict[WebSocket, dict]] = {}
def allow_move_request(move_times: deque, current_time: float) -> bool:
    while move_times and current_time - move_times[0] >= 1:
        move_times.popleft()
    if len(move_times) >= 20:
        return False
    move_times.append(current_time)
    return True

def choose_spawn(event_id: int, room_id: str, spawn_id: str):
    room_config = ROOMS[room_id]
    spawn = safe_spawn(room_config, spawn_id)
    occupied = [p for p in rooms.get(event_id, {}).values() if p['room_id'] == room_id]
    for ox, oy in ((0,0),(-72,0),(72,0),(0,-72),(0,72),(-72,-72),(72,-72)):
        x, y = spawn['x'] + ox, spawn['y'] + oy
        if not blocked(room_config, x, y) and not any(math.hypot(p['x']-x,p['y']-y) < RADIUS*2+8 for p in occupied):
            return {**spawn, 'x': x, 'y': y}
    return spawn

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
        try: await peer.send_json({'type': 'presence', 'world_revision': REVISION, 'participants': visible})
        except Exception: members.pop(peer, None)
def room_access(event_id, user_id):
    with SessionLocal() as db:
        event = db.get(Event, event_id)
        eligible = registration(db, event_id, user_id)
        if not event or not event.published or not eligible:
            return None
        return aware(event.starts_at)

@app.websocket('/ws/events/{event_id}')
async def room(ws: WebSocket, event_id: int, token: str):
    with SessionLocal() as db:
        try: user = get_user(token, db)
        except HTTPException: await ws.close(code=4401); return
        e = db.get(Event, event_id); reg = registration(db, event_id, user.id)
        if not e or not e.published or not reg or aware(e.starts_at) <= now(): await ws.close(code=4403); return
        deadline = aware(e.starts_at)
        spawn = choose_spawn(event_id, 'plaza', 'south_event_entrance')
        profile = db.get(V2Profile, user.id)
        personality = (profile.data or {}).get('personality_result') if profile else None
        person = {**public_user(user), 'personality': personality or reg.personality, 'x': spawn['x'], 'y': spawn['y'], 'direction': spawn['facing'], 'walking': False, 'room_id': 'plaza', 'seat_group': None, 'seat_id': None, 'seat_anchor': None}
    await ws.accept(); rooms.setdefault(event_id, {})[ws] = person; await room_snapshot(event_id)
    last_move = asyncio.get_running_loop().time()
    last_seq = -1
    move_times = deque()
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
                # Direct room selection exists only for local development diagnostics.
                if os.getenv('WORLD_ALLOW_ROOM_SWITCH') == '1' and data.get('room_id') in ROOMS:
                    person['room_id'] = data['room_id']; spawn = safe_spawn(ROOMS[person['room_id']], 'default')
                    person['x'], person['y'], person['direction'] = spawn['x'], spawn['y'], spawn['facing']
                    person.update(seat_group=None, seat_id=None, seat_anchor=None)
                    await ws.send_json({'type':'room_changed','room_id':person['room_id'],'spawn_id':'default','x':person['x'],'y':person['y'],'direction':person['direction']})
                    await room_snapshot(event_id)
                else:
                    await ws.send_json({'type':'world_error','code':'room_switch_disabled','message':'Use the room portals to travel.'})
            elif data.get('type') == 'move':
                try:
                    x, y = float(data['x']), float(data['y'])
                    seq = data.get('seq')
                    if not isinstance(seq, int) or isinstance(seq, bool) or seq <= last_seq:
                        await ws.send_json({'type':'position','seq':seq,'x':person['x'],'y':person['y'],'accepted':False}); continue
                    last_seq = seq
                    current_time = asyncio.get_running_loop().time()
                    if not allow_move_request(move_times, current_time):
                        await ws.send_json({'type':'position','seq':seq,'x':person['x'],'y':person['y'],'accepted':False}); continue
                    if not math.isfinite(x) or not math.isfinite(y):
                        await ws.send_json({'type':'position','seq':data.get('seq'),'x':person['x'],'y':person['y'],'accepted':False}); continue
                    elapsed = max(0.0, min(1.0, current_time - last_move))
                    distance = math.hypot(x-person['x'], y-person['y'])
                    reachable = WALK_SPEED * elapsed + 2.5
                    accepted = distance <= reachable and in_bounds(ROOMS[person['room_id']], x, y)
                    if accepted:
                        person['x'], person['y'] = swept_move(ROOMS[person['room_id']], (person['x'], person['y']), (x, y))
                        accepted = math.hypot(x-person['x'], y-person['y']) < 0.01
                    last_move = current_time
                    person['direction'] = data.get('direction') if data.get('direction') in ('up', 'down', 'left', 'right') else 'down'
                    person['walking'] = data.get('walking') is True and accepted
                    if accepted and distance > 0.5: person.update(seat_group=None, seat_id=None, seat_anchor=None)
                except (ValueError, TypeError, KeyError): continue
                await ws.send_json({'type':'position','seq':data.get('seq'),'x':person['x'],'y':person['y'],'accepted':accepted})
                await room_snapshot(event_id)
            elif data.get('type') == 'portal_enter':
                room_config = ROOMS[person['room_id']]
                portal = next((p for p in room_config['portals'] if p['id'] == data.get('portal_id')), None)
                if not portal or not shape_contains(portal['trigger'], person['x'], person['y'], 42):
                    await ws.send_json({'type':'world_error','code':'portal_out_of_range','message':'Move closer to enter.'}); continue
                destination = portal['destination']; next_room = ROOMS[destination['roomId']]
                spawn = choose_spawn(event_id, destination['roomId'], destination['spawnId'])
                x, y = spawn['x'], spawn['y']
                person.update(room_id=destination['roomId'],x=x,y=y,direction=spawn['facing'],walking=False,seat_group=None,seat_id=None,seat_anchor=None)
                last_move = asyncio.get_running_loop().time()
                await ws.send_json({'type':'room_changed','room_id':person['room_id'],'spawn_id':spawn['id'],'x':x,'y':y,'direction':spawn['facing']})
                await room_snapshot(event_id)
            elif data.get('type') == 'interact':
                room_config = ROOMS[person['room_id']]
                action = next((a for a in room_config['interactions'] if a['id'] == data.get('interaction_id')), None)
                eligible = [a for a in room_config['interactions'] if math.hypot(a['anchor']['x']-person['x'], a['anchor']['y']-person['y']) <= a['radius']]
                eligible.sort(key=lambda a: (-a['priority'], math.hypot(a['anchor']['x']-person['x'], a['anchor']['y']-person['y'])))
                if not action or not eligible or action['id'] != eligible[0]['id']:
                    await ws.send_json({'type':'world_error','code':'interaction_out_of_range','message':'Move closer to use this.'}); continue
                anchor = action.get('anchor')
                seat_id = None
                if action['action']['type'] == 'seat':
                    group = action['action'].get('seatGroup')
                    candidates = [s for s in room_config.get('seats',[]) if s['id'].startswith(group+'_')]
                    occupied = {p.get('seat_id') for p in rooms.get(event_id,{}).values() if p is not person and p['room_id'] == person['room_id'] and p.get('seat_id')}
                    free = [s for s in candidates if s['id'] not in occupied]
                    if not free:
                        await ws.send_json({'type':'world_error','code':'seats_full','message':'All nearby seats are occupied.'}); continue
                    seat = min(free,key=lambda s: math.hypot(s['x']-person['x'],s['y']-person['y']))
                    seat_id, anchor = seat['id'], {'x':seat['x'],'y':seat['y'],'facing':seat['facing']}
                    person['seat_group'], person['seat_id'], person['seat_anchor'] = group, seat_id, anchor
                    person.update(x=seat['x'], y=seat['y'], direction=seat['facing'], walking=False)
                    await ws.send_json({'type':'position','x':person['x'],'y':person['y'],'direction':person['direction'],'accepted':True})
                await ws.send_json({'type':'interaction_result','interaction_id':action['id'],'action':action['action'],'label':action['label'],'payload':{'panel':action['action'].get('panel'),'anchor':anchor,'seat_group':person.get('seat_group'),'seat_id':seat_id}})
                await room_snapshot(event_id)
            elif data.get('type') == 'chat':
                text = str(data.get('text', '')).strip()[:500]
                target_id = data.get('target_id')
                targets = [(peer, other) for peer, other in rooms.get(event_id, {}).items()
                           if other['id'] == target_id and other['id'] != person['id'] and other['room_id'] == person['room_id']
                           and math.hypot(other['x'] - person['x'], other['y'] - person['y']) <= CHAT_RADIUS]
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
