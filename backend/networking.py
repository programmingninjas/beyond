"""Cached matching and consented pet conversation services."""
import asyncio
from datetime import datetime, timezone
from typing import Literal
from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint, or_
from sqlalchemy.orm import Mapped, Session, mapped_column
from ai_service import generate, Match, PetConversation


def install(app, Base, SessionLocal, current_user, User, Event, Registration, Connection, Profile, Persona, Block, Introduction):
    class Job(Base):
        __tablename__ = 'v2_jobs'
        id: Mapped[int] = mapped_column(primary_key=True)
        kind: Mapped[str] = mapped_column(String(30))
        event_id: Mapped[int] = mapped_column(ForeignKey('events.id'), index=True)
        user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
        target_id: Mapped[int] = mapped_column(Integer, default=0)
        state: Mapped[str] = mapped_column(String(30), default='pending')
        error: Mapped[str] = mapped_column(String(300), default='')
        created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    class Recommendation(Base):
        __tablename__ = 'v2_recommendations'
        __table_args__ = (UniqueConstraint('event_id', 'user_id', 'candidate_id'),)
        id: Mapped[int] = mapped_column(primary_key=True)
        event_id: Mapped[int] = mapped_column(ForeignKey('events.id'), index=True)
        user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
        candidate_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
        data: Mapped[dict] = mapped_column(JSON)
        created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    class Transcript(Base):
        __tablename__ = 'v2_transcripts'
        introduction_id: Mapped[int] = mapped_column(ForeignKey('v2_introductions.id'), primary_key=True)
        data: Mapped[dict] = mapped_column(JSON)
        requester_decision: Mapped[str] = mapped_column(String(20), default='pending')
        recipient_decision: Mapped[str] = mapped_column(String(20), default='pending')
        created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def session():
        with SessionLocal() as db: yield db
    def block(db, a, b):
        return db.query(Block).filter(or_((Block.user_id == a) & (Block.other_id == b), (Block.user_id == b) & (Block.other_id == a))).first() is not None
    def eligible(db, event, uid):
        e = db.get(Event, event); reg = db.query(Registration).filter_by(event_id=event, user_id=uid).first()
        if not e or not e.published or not reg or not reg.personality: raise HTTPException(403, 'Complete event registration and quiz first')
        return reg
    def context(db, event, uid):
        user = db.get(User, uid); profile = db.get(Profile, uid); persona = db.query(Persona).filter_by(event_id=event, user_id=uid).first()
        reg = db.query(Registration).filter_by(event_id=event, user_id=uid).first()
        return {'name': user.name, 'bio': user.bio, 'interests': user.interests, **(profile.data if profile else {}), **(persona.data if persona else {}), 'quiz_result': reg.personality if reg else ''}
    def queue(db, kind, event, uid, target=0):
        job = db.query(Job).filter_by(kind=kind, event_id=event, user_id=uid, target_id=target).filter(Job.state.in_(['pending','running'])).first()
        if not job:
            job = Job(kind=kind, event_id=event, user_id=uid, target_id=target, state='pending', error=''); db.add(job); db.commit(); db.refresh(job)
        return job
    def job_data(job): return {'id': job.id, 'state': job.state, 'error': job.error}
    def authorized_intro(db, intro_id, uid):
        intro = db.get(Introduction, intro_id)
        if not intro or uid not in (intro.requester_id, intro.recipient_id) or block(db, intro.requester_id, intro.recipient_id): raise HTTPException(404, 'Introduction not found')
        return intro

    @app.post('/v2/events/{event_id}/matching/refresh')
    def refresh(event_id: int, user: User = Depends(current_user), db: Session = Depends(session)):
        eligible(db,event_id,user.id)
        return job_data(queue(db,'matching',event_id,user.id))
    @app.post('/v2/events/{event_id}/matching/refresh-all')
    def refresh_all(event_id: int, user: User = Depends(current_user), db: Session = Depends(session)):
        event=db.get(Event,event_id)
        if not event or event.owner_id != user.id: raise HTTPException(403,'Only the event organizer can refresh everyone')
        jobs=[]
        for reg in db.query(Registration).filter_by(event_id=event_id).filter(Registration.personality.is_not(None)).all():
            jobs.append(job_data(queue(db,'matching',event_id,reg.user_id)))
        return {'jobs':jobs}
    @app.get('/v2/events/{event_id}/matching')
    def matches(event_id: int, user: User = Depends(current_user), db: Session = Depends(session)):
        eligible(db,event_id,user.id)
        job = db.query(Job).filter_by(kind='matching',event_id=event_id,user_id=user.id).order_by(Job.id.desc()).first()
        result = []
        for row in db.query(Recommendation).filter_by(event_id=event_id,user_id=user.id).all():
            other = db.get(User,row.candidate_id); p = db.get(Profile,row.candidate_id)
            if not other or (p and not p.discoverable) or block(db,user.id,other.id): continue
            try: eligible(db,event_id,other.id)
            except HTTPException: continue
            result.append({'id':other.id,'name':other.name,'bio':other.bio,'avatar':(p.data.get('avatar','red-panda') if p else 'red-panda'), **row.data, 'calculated_at':row.created_at.isoformat()})
        return {'job':job_data(job) if job else None, 'matches':sorted(result,key=lambda x:-x['score'])}
    @app.get('/v2/events/{event_id}/directory')
    def directory(event_id: int, user: User = Depends(current_user), db: Session = Depends(session)):
        eligible(db,event_id,user.id); result=[]
        for reg in db.query(Registration).filter_by(event_id=event_id).filter(Registration.user_id != user.id, Registration.personality.is_not(None)).all():
            p = db.get(Profile,reg.user_id); other = db.get(User,reg.user_id)
            if other and not (p and not p.discoverable) and not block(db,user.id,other.id): result.append({'id':other.id,'name':other.name,'bio':other.bio})
        return result
    @app.post('/v2/introductions/{intro_id}/generate')
    def start_conversation(intro_id: int, user: User = Depends(current_user), db: Session = Depends(session)):
        intro=authorized_intro(db,intro_id,user.id)
        if intro.state != 'approved': raise HTTPException(409,'Both owners must approve first')
        if db.get(Transcript,intro_id): return {'state':'complete'}
        return job_data(queue(db,'conversation',intro.event_id,intro.requester_id,intro.id))
    @app.get('/v2/introductions/{intro_id}/conversation')
    def conversation(intro_id: int, user: User = Depends(current_user), db: Session = Depends(session)):
        intro=authorized_intro(db,intro_id,user.id)
        if intro.state != 'approved': raise HTTPException(409,'Conversation unavailable')
        row=db.get(Transcript,intro.id)
        job=db.query(Job).filter_by(kind='conversation',target_id=intro.id).order_by(Job.id.desc()).first()
        return {'conversation':row.data if row else None,'job':job_data(job) if job else None,'your_decision':(row.requester_decision if intro.requester_id==user.id else row.recipient_decision) if row else 'pending'}
    class Decision(BaseModel):
        decision: Literal['accept','decline','withdraw']
    @app.post('/v2/introductions/{intro_id}/decision')
    def decide(intro_id: int, body: Decision, user: User = Depends(current_user), db: Session = Depends(session)):
        intro=authorized_intro(db,intro_id,user.id); row=db.get(Transcript,intro_id)
        if intro.state != 'approved' or not row: raise HTTPException(409,'Review the conversation first')
        if row.requester_decision == 'accept' and row.recipient_decision == 'accept': raise HTTPException(409,'Introduction already accepted')
        value={'accept':'accept','decline':'decline','withdraw':'pending'}[body.decision]
        if user.id==intro.requester_id: row.requester_decision=value
        else: row.recipient_decision=value
        connected=row.requester_decision=='accept' and row.recipient_decision=='accept'
        if connected:
            low,high=sorted([intro.requester_id,intro.recipient_id]); c=db.query(Connection).filter_by(low_id=low,high_id=high).first()
            if c: c.accepted=True
            else: db.add(Connection(low_id=low,high_id=high,requester_id=intro.requester_id,accepted=True))
        db.commit(); return {'your_decision':value,'connected':connected}

    def run_job(job_id):
        with SessionLocal() as db:
            job=db.get(Job,job_id)
            if not job or job.state != 'pending': return
            job.state='running'; db.commit()
            try:
                if job.kind=='matching':
                    eligible(db,job.event_id,job.user_id)
                    own=context(db,job.event_id,job.user_id); rows=[]; snapshots={job.user_id: own}
                    regs=db.query(Registration).filter_by(event_id=job.event_id).filter(Registration.user_id != job.user_id,Registration.personality.is_not(None)).limit(50).all()
                    for reg in regs:
                        p=db.get(Profile,reg.user_id)
                        if (p and not p.discoverable) or block(db,job.user_id,reg.user_id): continue
                        candidate=context(db,job.event_id,reg.user_id); snapshots[reg.user_id]=candidate
                        match,meta=generate(Match,'Assess the networking relationship. Assign one circle based on evidence, not score. Scores 0-100 in order: goals, needs and offerings, shared interests, collaboration, event relevance. Give evidence and an honest reason. Avoid recommending unsupported relationships.',{'viewer':own,'candidate':candidate})
                        score=round(sum(a*b for a,b in zip(match.scores,[.25,.30,.20,.15,.10])))
                        if score < 25: continue
                        rows.append(Recommendation(event_id=job.event_id,user_id=job.user_id,candidate_id=reg.user_id,data={**match.model_dump(),'score':score,'model':meta['model'],'usage':meta['usage']}))
                    db.expire_all()
                    if any(context(db,job.event_id,uid) != original for uid,original in snapshots.items()): raise RuntimeError('Profiles changed during matching; please refresh')
                    db.query(Recommendation).filter_by(event_id=job.event_id,user_id=job.user_id).delete()
                    db.add_all(rows)
                elif job.kind=='conversation':
                    intro=authorized_intro(db,job.target_id,job.user_id)
                    if intro.state!='approved': raise RuntimeError('Consent is no longer valid')
                    a=context(db,intro.event_id,intro.requester_id); b=context(db,intro.event_id,intro.recipient_id)
                    a={k:v for k,v in a.items() if k in intro.requester_sharing}; b={k:v for k,v in b.items() if k in intro.recipient_sharing}
                    result,meta=generate(PetConversation,'Write four to six short alternating pet messages grounded only in the approved fields. Discuss potential value without forcing a positive conclusion. Do not commit either person to anything.',{'requester':a,'recipient':b})
                    db.refresh(intro)
                    if intro.state!='approved' or block(db,intro.requester_id,intro.recipient_id): raise RuntimeError('Consent is no longer valid')
                    if not db.get(Transcript,intro.id): db.add(Transcript(introduction_id=intro.id,data={**result.model_dump(),'model':meta['model'],'usage':meta['usage']}))
                job.state='complete'; db.commit()
            except Exception as exc:
                db.rollback(); job=db.get(Job,job_id)
                if job: job.state='failed'; job.error=str(exc)[:300]; db.commit()
    async def worker():
        while True:
            with SessionLocal() as db:
                job=db.query(Job).filter_by(state='pending').order_by(Job.id).first(); job_id=job.id if job else None
            if job_id: await asyncio.to_thread(run_job,job_id)
            else: await asyncio.sleep(2)
    @app.on_event('startup')
    async def start_worker():
        with SessionLocal() as db:
            db.query(Job).filter_by(state='running').update({'state':'pending'}); db.commit()
        app.state.network_worker=asyncio.create_task(worker())
    @app.on_event('shutdown')
    async def stop_worker():
        app.state.network_worker.cancel()
    return Job, Recommendation, Transcript
