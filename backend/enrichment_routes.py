from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import enrichment


def install(app, db_session, current_user, User, Profile, secret):
    class PreviewInput(BaseModel):
        url: str = Field(min_length=1, max_length=500)
        consent: bool
    class ApplyInput(BaseModel):
        draft_token: str = Field(min_length=1, max_length=60000)
        fields: dict[str, str] = Field(min_length=1, max_length=11)

    def current_values(user, profile):
        data = profile.data if profile else {}
        return {key: (getattr(user, key) if key in ('bio','interests') else data.get(key, '')) or '' for key in enrichment.ProfileSuggestions.model_fields}

    @app.post('/v2/profile/enrichment/preview')
    def preview(body: PreviewInput, user: User = Depends(current_user), db: Session = Depends(db_session)):
        if not body.consent: raise HTTPException(403, 'Explicit consent is required for each import')
        try:
            url = enrichment.validate_source(body.url)
            suggestions, meta = enrichment.preview(url)
        except ValueError as exc: raise HTTPException(422, str(exc)) from exc
        except RuntimeError as exc: raise HTTPException(503, str(exc)) from exc
        suggestions = {k:v.strip() for k,v in suggestions.items() if v.strip()}
        if not suggestions: raise HTTPException(422, 'No profile suggestions were found for this link')
        initial_all = current_values(user, db.get(Profile,user.id))
        initial = {key:initial_all[key] for key in suggestions}
        token = jwt.encode({'sub':str(user.id), 'purpose':'profile_import', 'source':url, 'suggestions':suggestions, 'initial':initial, 'exp':datetime.now(timezone.utc)+timedelta(minutes=30)}, secret, algorithm='HS256')
        return {'source_url':url, 'suggestions':suggestions, 'current':{key:initial[key] for key in suggestions}, 'draft_token':token, 'model':meta['model']}

    @app.post('/v2/profile/enrichment/apply')
    def apply(body: ApplyInput, user: User = Depends(current_user), db: Session = Depends(db_session)):
        try:
            draft = jwt.decode(body.draft_token, secret, algorithms=['HS256'])
            if draft.get('purpose') != 'profile_import' or draft.get('sub') != str(user.id): raise ValueError()
        except (jwt.PyJWTError, ValueError): raise HTTPException(400, 'Import preview is invalid or expired; generate a new preview')
        original = draft['suggestions']
        if not set(body.fields) <= set(original): raise HTTPException(422, 'Only suggested fields may be applied')
        try:
            values = enrichment.ProfileSuggestions.model_validate({**{k:'' for k in enrichment.ProfileSuggestions.model_fields}, **body.fields}).model_dump()
        except ValueError as exc: raise HTTPException(422, 'One or more selected fields are too long') from exc
        row = db.get(Profile, user.id)
        current = current_values(user, row)
        if any(current[k] != draft['initial'][k] for k in body.fields): raise HTTPException(409, 'Your profile changed after this preview. Generate a new preview before applying it.')
        if any(not values[k].strip() for k in body.fields): raise HTTPException(422, 'Selected fields must not be empty')
        if not row: row=Profile(user_id=user.id, data={}, discoverable=True); db.add(row)
        data = dict(row.data or {}); sources = dict(data.get('enrichment_sources') or {})
        at = datetime.now(timezone.utc).isoformat()
        for key in body.fields:
            value = values[key].strip()
            if key in ('bio','interests'): setattr(user, key, value)
            else: data[key] = value
            sources[key] = {'url':draft['source'], 'imported_at':at, 'user_edited': value != original[key]}
        data['enrichment_sources'] = sources; row.data = data
        db.commit()
        return {'applied':list(body.fields), 'source_url':draft['source']}
