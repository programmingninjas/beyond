"""V2 networking profiles and consent, kept separate from the MVP tables."""
from datetime import datetime, timezone
from typing import Literal

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, or_
from sqlalchemy.orm import Mapped, mapped_column, Session

SHARE_FIELDS = ['name', 'bio', 'interests', 'headline', 'role', 'organization', 'skills', 'expertise', 'industry', 'attending', 'seeking', 'offering', 'projects', 'topics']


def install(app, Base, db_session, current_user, User, Event, Registration, Connection):
    class Profile(Base):
        __tablename__ = 'v2_profiles'
        user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
        data: Mapped[dict] = mapped_column(JSON, default=dict)
        discoverable: Mapped[bool] = mapped_column(Boolean, default=True)

    class Persona(Base):
        __tablename__ = 'v2_personas'
        __table_args__ = (UniqueConstraint('event_id', 'user_id'),)
        id: Mapped[int] = mapped_column(primary_key=True)
        event_id: Mapped[int] = mapped_column(ForeignKey('events.id'), index=True)
        user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
        data: Mapped[dict] = mapped_column(JSON, default=dict)

    class Block(Base):
        __tablename__ = 'v2_blocks'
        __table_args__ = (UniqueConstraint('user_id', 'other_id'),)
        id: Mapped[int] = mapped_column(primary_key=True)
        user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
        other_id: Mapped[int] = mapped_column(ForeignKey('users.id'))

    class Introduction(Base):
        __tablename__ = 'v2_introductions'
        id: Mapped[int] = mapped_column(primary_key=True)
        event_id: Mapped[int] = mapped_column(ForeignKey('events.id'), index=True)
        requester_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
        recipient_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
        state: Mapped[str] = mapped_column(String(30), default='pending')
        requester_sharing: Mapped[list] = mapped_column(JSON, default=list)
        recipient_sharing: Mapped[list] = mapped_column(JSON, default=list)
        created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    class ProfileInput(BaseModel):
        phone: str = Field(default='', max_length=40)
        projects: str = Field(default='', max_length=2000)
        experience: str = Field(default='', max_length=2000)
        achievements: str = Field(default='', max_length=2000)
        website: str = Field(default='', max_length=500)
        additional_social: str = Field(default='', max_length=1000)
        networking_goals: str = Field(default='', max_length=2000)
        headline: str = Field(default='', max_length=200)
        role: str = Field(default='', max_length=200)
        organization: str = Field(default='', max_length=200)
        skills: str = Field(default='', max_length=1000)
        expertise: str = Field(default='', max_length=1000)
        industry: str = Field(default='', max_length=200)
        avatar: Literal['red-panda', 'axolotl', 'sunda-pangolin', 'kakapo', 'vaquita'] = 'red-panda'
        pet_name: str = Field(default='Spark', min_length=1, max_length=60)
        pet_color: str = Field(default='#c4b5fd', pattern=r'^#[0-9a-fA-F]{6}$')
        pet_style: Literal['curious', 'playful', 'calm', 'energetic'] = 'curious'
        discoverable: bool = True

    class PersonaInput(BaseModel):
        attending: str = Field(default='', max_length=2000)
        seeking: str = Field(default='', max_length=2000)
        offering: str = Field(default='', max_length=2000)
        projects: str = Field(default='', max_length=2000)
        topics: str = Field(default='', max_length=2000)

    class ShareInput(BaseModel):
        fields: list[Literal['name', 'bio', 'interests', 'headline', 'role', 'organization', 'skills', 'expertise', 'industry', 'attending', 'seeking', 'offering', 'projects', 'topics']] = Field(default_factory=list, max_length=15)

    class PetSharingInput(BaseModel):
        fields: list[Literal['name', 'bio', 'interests', 'headline', 'role', 'organization', 'skills', 'expertise', 'industry', 'attending', 'seeking', 'offering', 'projects', 'topics']] = Field(max_length=15)

    def eligible(db, event_id, user_id):
        event = db.get(Event, event_id)
        reg = db.query(Registration).filter_by(event_id=event_id, user_id=user_id).first()
        if not event or not event.published or not reg:
            raise HTTPException(403, 'Register for the event first')
        return reg

    def blocked(db, first, second):
        return db.query(Block).filter(or_((Block.user_id == first) & (Block.other_id == second), (Block.user_id == second) & (Block.other_id == first))).first() is not None

    @app.get('/v2/profile')
    def get_profile(user: User = Depends(current_user), db: Session = Depends(db_session)):
        row = db.get(Profile, user.id)
        from profile_rules import completion
        data = row.data if row else {}
        return {**ProfileInput().model_dump(), **data, 'discoverable': row.discoverable if row else True, 'completion': completion(user, data)}

    @app.put('/v2/profile')
    def put_profile(body: ProfileInput, user: User = Depends(current_user), db: Session = Depends(db_session)):
        row = db.get(Profile, user.id)
        if not row:
            row = Profile(user_id=user.id); db.add(row)
        previous = row.data or {}
        updated = body.model_dump(exclude={'discoverable'})
        sources = dict(previous.get('enrichment_sources') or {})
        for key in updated:
            if key in sources and updated[key] != previous.get(key, ''): sources.pop(key, None)
        updated['enrichment_sources'] = sources
        if previous.get('personality_result'): updated['personality_result'] = previous['personality_result']
        if previous.get('pet_sharing') is not None: updated['pet_sharing'] = previous['pet_sharing']
        row.data = updated; row.discoverable = body.discoverable
        db.commit()
        return body.model_dump()

    @app.get('/v2/profile/pet-sharing')
    def get_pet_sharing(user: User = Depends(current_user), db: Session = Depends(db_session)):
        return {'fields': SHARE_FIELDS}

    @app.put('/v2/profile/pet-sharing')
    def put_pet_sharing(body: PetSharingInput, user: User = Depends(current_user), db: Session = Depends(db_session)):
        row = db.get(Profile, user.id)
        if not row:
            row = Profile(user_id=user.id, data={}); db.add(row)
        data = dict(row.data or {})
        data['pet_sharing'] = SHARE_FIELDS
        row.data = data
        db.commit()
        return {'fields': SHARE_FIELDS}

    @app.get('/v2/events/{event_id}/persona')
    def get_persona(event_id: int, user: User = Depends(current_user), db: Session = Depends(db_session)):
        eligible(db, event_id, user.id)
        row = db.query(Persona).filter_by(event_id=event_id, user_id=user.id).first()
        return row.data if row else PersonaInput().model_dump()

    @app.put('/v2/events/{event_id}/persona')
    def put_persona(event_id: int, body: PersonaInput, user: User = Depends(current_user), db: Session = Depends(db_session)):
        eligible(db, event_id, user.id)
        row = db.query(Persona).filter_by(event_id=event_id, user_id=user.id).first()
        if not row:
            row = Persona(event_id=event_id, user_id=user.id); db.add(row)
        row.data = body.model_dump(); db.commit()
        return row.data

    @app.post('/v2/blocks/{other_id}')
    def block(other_id: int, user: User = Depends(current_user), db: Session = Depends(db_session)):
        if other_id == user.id or not db.get(User, other_id): raise HTTPException(400, 'Invalid participant')
        if not db.query(Block).filter_by(user_id=user.id, other_id=other_id).first(): db.add(Block(user_id=user.id, other_id=other_id))
        for intro in db.query(Introduction).filter(or_((Introduction.requester_id == user.id) & (Introduction.recipient_id == other_id), (Introduction.requester_id == other_id) & (Introduction.recipient_id == user.id)), Introduction.state.in_(['pending', 'approved'])).all():
            intro.state = 'cancelled'
        db.commit(); return {'ok': True}

    @app.post('/v2/events/{event_id}/introductions/{other_id}')
    def request_introduction(event_id: int, other_id: int, body: ShareInput, user: User = Depends(current_user), db: Session = Depends(db_session)):
        eligible(db, event_id, user.id); eligible(db, event_id, other_id)
        other_profile = db.get(Profile, other_id)
        if other_id == user.id or blocked(db, user.id, other_id) or (other_profile and not other_profile.discoverable): raise HTTPException(403, 'Participant unavailable')
        existing = db.query(Introduction).filter_by(event_id=event_id).filter(or_((Introduction.requester_id == user.id) & (Introduction.recipient_id == other_id), (Introduction.requester_id == other_id) & (Introduction.recipient_id == user.id)), Introduction.state.in_(['pending', 'approved'])).first()
        if existing: raise HTTPException(409, 'An introduction is already pending')
        requester_profile = db.get(Profile, user.id)
        allowed_fields = SHARE_FIELDS
        row = Introduction(event_id=event_id, requester_id=user.id, recipient_id=other_id, requester_sharing=allowed_fields, recipient_sharing=[], state='pending')
        db.add(row); db.commit(); db.refresh(row); return {'id': row.id, 'state': row.state}

    @app.get('/v2/introductions')
    def list_introductions(user: User = Depends(current_user), db: Session = Depends(db_session)):
        rows = db.query(Introduction).filter(or_(Introduction.requester_id == user.id, Introduction.recipient_id == user.id)).order_by(Introduction.id.desc()).all()
        return [{'id': x.id, 'event_id': x.event_id, 'other': db.get(User, x.recipient_id if x.requester_id == user.id else x.requester_id).name, 'incoming': x.recipient_id == user.id, 'state': ('pending' if x.state == 'declined' and x.requester_id == user.id else x.state), 'sharing': x.recipient_sharing if x.recipient_id == user.id else x.requester_sharing} for x in rows if x.state != 'cancelled' and (x.state != 'declined' or x.requester_id == user.id)]

    @app.post('/v2/introductions/{intro_id}/approve')
    def approve(intro_id: int, body: ShareInput, user: User = Depends(current_user), db: Session = Depends(db_session)):
        row = db.get(Introduction, intro_id)
        if not row or row.recipient_id != user.id: raise HTTPException(404, 'Introduction not found')
        if row.state != 'pending' or blocked(db, row.requester_id, row.recipient_id): raise HTTPException(409, 'Introduction is no longer pending')
        eligible(db, row.event_id, row.requester_id); eligible(db, row.event_id, row.recipient_id)
        profile = db.get(Profile, user.id)
        allowed_fields = SHARE_FIELDS
        if not set(body.fields).issubset(allowed_fields): raise HTTPException(422, 'You can only share fields enabled in your pet sharing settings')
        row.recipient_sharing = body.fields; row.state = 'approved'; db.commit()
        return {'state': row.state, 'message': 'Consent recorded. Either owner can start the pet conversation.'}

    @app.post('/v2/introductions/{intro_id}/decline')
    def decline(intro_id: int, user: User = Depends(current_user), db: Session = Depends(db_session)):
        row = db.get(Introduction, intro_id)
        if not row or row.recipient_id != user.id: raise HTTPException(404, 'Introduction not found')
        if row.state != 'pending': raise HTTPException(409, 'Introduction is no longer pending')
        row.state = 'declined'; db.commit(); return {'ok': True}

    return Profile, Persona, Block, Introduction
