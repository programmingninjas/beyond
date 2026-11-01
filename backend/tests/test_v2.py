import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(tempfile.mkdtemp()) / 'test.db')
from main import app, engine
from sqlalchemy import text


@pytest.fixture
def client():
    __import__("main").startup()
    with engine.begin() as conn:
        for table in reversed(__import__('main').Base.metadata.sorted_tables):
            conn.execute(table.delete())
    with TestClient(app) as c:
        yield c


def complete_basic(client, headers):
    user = client.get('/me', headers=headers).json()
    assert client.put('/me', headers=headers, json={'name':user['name'], 'bio':'A' * 100, 'interests':'AI, design', 'profile_url':'https://example.com/profile'}).status_code == 200
    assert client.put('/v2/profile', headers=headers, json={'phone':'+1234567890'}).status_code == 200

def test_profile_persona_and_consent(client):
    def signup(name):
        response = client.post('/auth/signup', json={'name': name, 'email': f'{name}@example.com', 'password': 'testpassword'})
        assert response.status_code == 200, response.text
        return {'Authorization': 'Bearer ' + response.json()['token']}
    a, b, c = signup('alice'), signup('bob'), signup('carol')
    start = datetime.now(timezone.utc) + timedelta(days=1)
    event = client.post('/events', headers=a, json={'title':'Test', 'starts_at':start.isoformat(), 'ends_at':(start+timedelta(hours=2)).isoformat(), 'published':True}).json()['id']
    for headers in (a, b, c):
        complete_basic(client,headers)
        assert client.post(f'/events/{event}/register', headers=headers).status_code == 200
    assert client.put('/v2/profile', headers=a, json={'headline':'Founder','avatar':'axolotl'}).status_code == 200
    assert client.get('/v2/profile', headers=a).json()['headline'] == 'Founder'
    assert client.put('/v2/profile/pet-sharing', headers=a, json={'fields':['name','seeking']}).status_code == 200
    assert client.put('/v2/profile/pet-sharing', headers=b, json={'fields':['name']}).status_code == 200
    assert client.put(f'/v2/events/{event}/persona', headers=a, json={'seeking':'Designers'}).status_code == 200
    assert client.get(f'/v2/events/{event}/persona', headers=a).json()['seeking'] == 'Designers'
    bob_id = client.get('/me', headers=b).json()['id']
    req = client.post(f'/v2/events/{event}/introductions/{bob_id}', headers=a, json={'fields':['name','seeking']})
    assert req.status_code == 200, req.text
    intro = req.json()['id']
    assert client.post(f'/v2/introductions/{intro}/approve', headers=c, json={'fields':['name']}).status_code == 404
    assert client.post(f'/v2/introductions/{intro}/approve', headers=b, json={'fields':['name']}).json()['state'] == 'approved'
    assert client.get('/v2/introductions', headers=a).json()[0]['sharing'] == ['name','seeking']
    assert client.post(f'/v2/blocks/{bob_id}', headers=a).status_code == 200
    assert client.get('/v2/introductions', headers=a).json() == []
    assert all(p['id'] != bob_id for p in client.get(f'/v2/events/{event}/directory', headers=a).json())
    assert client.delete(f'/events/{event}', headers=a).status_code == 200


def test_migration_preserves_legacy_rows():
    from main import Base
    from migrations import migrate
    from sqlalchemy import create_engine, select
    from main import User
    test_engine = create_engine('sqlite:///:memory:')
    legacy = [table for table in Base.metadata.sorted_tables if not table.name.startswith('v2_')]
    Base.metadata.create_all(test_engine, tables=legacy)
    with test_engine.begin() as conn:
        conn.execute(User.__table__.insert().values(id=100, email='old@example.com', password='hash', name='Existing', bio='', interests='', profile_url='', enrichment_consent=False))
    tables = ['v2_profiles', 'v2_personas', 'v2_blocks', 'v2_introductions']
    migrate(test_engine, Base, tables)
    migrate(test_engine, Base, tables)
    with test_engine.connect() as conn:
        assert conn.execute(select(User.__table__.c.name)).scalar_one() == 'Existing'
        assert conn.execute(text('SELECT count(*) FROM schema_versions')).scalar_one() == 3


def test_matching_and_conversation_are_cached_and_authorized(client, monkeypatch):
    import networking
    import time
    from ai_service import Match, PetConversation
    calls = []
    def fake_generate(kind, instructions, data):
        calls.append((kind.__name__, data))
        if kind is Match:
            return Match(scores=[80,90,70,80,60], evidence=['Shared AI interest'], explanation='They can collaborate.', conversation_starter='What are you building?'), {'model':'test','usage':{}}
        return PetConversation(messages=[{'speaker':'requester' if i % 2 == 0 else 'recipient','phase':'discovery','text':'Hello'} for i in range(4)], highlights=['Shared AI interest'], summary='They may collaborate.', outcome='potential'), {'model':'test','usage':{}}
    monkeypatch.setattr(networking, 'generate', fake_generate)
    def signup(name):
        return {'Authorization': 'Bearer ' + client.post('/auth/signup',json={'name':name,'email':f'{name}@example.com','password':'testpassword'}).json()['token']}
    a,b,c=signup('alice'),signup('bob'),signup('carol')
    start=datetime.now(timezone.utc)+timedelta(days=1)
    event=client.post('/events',headers=a,json={'title':'Test','starts_at':start.isoformat(),'ends_at':(start+timedelta(hours=1)).isoformat(),'published':True}).json()['id']
    for h in (a,b):
        complete_basic(client,h); client.post(f'/events/{event}/register',headers=h)
    bob=client.get('/me',headers=b).json()['id']
    client.put(f'/v2/events/{event}/persona',headers=a,json={'seeking':'A designer','offering':'Secret offer'})
    client.put('/v2/profile/pet-sharing',headers=a,json={'fields':['name','seeking']})
    client.put('/v2/profile/pet-sharing',headers=b,json={'fields':['name']})
    client.post(f'/v2/events/{event}/matching/refresh',headers=a)
    def await_value(url, headers, key):
        for _ in range(40):
            result=client.get(url,headers=headers).json()
            if result.get(key): return result
            time.sleep(.1)
        pytest.fail(str(result))
    match=await_value(f'/v2/events/{event}/matching',a,'matches')['matches'][0]
    assert match['circle']=='shared' and match['score']==79
    assert len(calls)==1
    intro=client.post(f'/v2/events/{event}/introductions/{bob}',headers=a,json={'fields':['name','seeking']}).json()['id']
    assert client.post(f'/v2/introductions/{intro}/generate',headers=a).status_code==409
    client.post(f'/v2/introductions/{intro}/approve',headers=b,json={'fields':['name']})
    client.post(f'/v2/introductions/{intro}/generate',headers=a)
    convo=await_value(f'/v2/introductions/{intro}/conversation',a,'conversation')
    assert convo['conversation']['summary']=='They may collaborate.'
    assert calls[-1][1]['requester']=={'name':'alice','seeking':'A designer'}
    assert client.get(f'/v2/introductions/{intro}/conversation',headers=c).status_code==404
    assert not client.post(f'/v2/introductions/{intro}/decision',headers=a,json={'decision':'accept'}).json()['connected']
    assert client.post(f'/v2/introductions/{intro}/decision',headers=b,json={'decision':'accept'}).json()['connected']
    assert client.get(f'/messages/{bob}',headers=a).status_code==200
    client.get(f'/v2/introductions/{intro}/conversation',headers=a)
    assert len(calls)==2


def test_room_transition_is_event_scoped(client, monkeypatch):
    monkeypatch.setenv('WORLD_ALLOW_ROOM_SWITCH', '1')
    token=client.post('/auth/signup',json={'name':'alex','email':'alex@example.com','password':'testpassword'}).json()['token']
    auth={'Authorization':'Bearer '+token}
    start=datetime.now(timezone.utc)+timedelta(days=1)
    event=client.post('/events',headers=auth,json={'title':'Test','starts_at':start.isoformat(),'ends_at':(start+timedelta(hours=1)).isoformat(),'published':True}).json()['id']
    complete_basic(client,auth)
    client.post(f'/events/{event}/register',headers=auth)
    with client.websocket_connect(f'/ws/events/{event}?token={token}') as ws:
        assert ws.receive_json()['participants'][0]['room_id']=='plaza'
        ws.send_json({'type':'room','room_id':'garden'})
        assert ws.receive_json()['room_id']=='garden'
        assert ws.receive_json()['participants'][0]['room_id']=='garden'


@pytest.mark.parametrize(('score', 'circle'), [(100, 'inner'), (81, 'inner'), (80, 'shared'), (61, 'shared'), (60, 'perspectives'), (41, 'perspectives'), (40, 'serendipity'), (0, 'serendipity')])
def test_circle_score_boundaries(score, circle):
    from networking import circle_for_score
    assert circle_for_score(score) == circle


def test_profile_completion_and_registration_questions(client):
    token=client.post('/auth/signup',json={'name':'Owner','email':'owner@example.com','password':'testpassword'}).json()['token']
    owner={'Authorization':'Bearer '+token}
    token2=client.post('/auth/signup',json={'name':'Attendee','email':'attendee@example.com','password':'testpassword'}).json()['token']
    attendee={'Authorization':'Bearer '+token2}
    start=datetime.now(timezone.utc)+timedelta(days=1)
    event=client.post('/events',headers=owner,json={'title':'Event','starts_at':start.isoformat(),'ends_at':(start+timedelta(hours=1)).isoformat(),'published':True}).json()['id']
    fields={'fields':[{'label':'Dietary needs','required':True},{'label':'Anything else?','required':False}]}
    assert client.put(f'/events/{event}/registration-fields',headers=attendee,json=fields).status_code==403
    assert client.put(f'/events/{event}/registration-fields',headers=owner,json=fields).status_code==200
    assert client.post(f'/events/{event}/register',headers=attendee,json={'answers':{'Dietary needs':'None'}}).status_code==403
    complete_basic(client,attendee)
    assert client.get('/v2/profile',headers=attendee).json()['completion']['score']==25
    assert client.post(f'/events/{event}/register',headers=attendee,json={'answers':{}}).status_code==422
    assert client.post(f'/events/{event}/register',headers=attendee,json={'answers':{'Dietary needs':'None'}}).status_code==200
    assert client.get(f'/events/{event}/registration-answers',headers=attendee).status_code==403
    assert client.get(f'/events/{event}/registration-answers',headers=owner).json()[0]['answers']=={'Dietary needs':'None'}
    assert client.put(f'/events/{event}/registration-fields',headers=owner,json=fields).status_code==409
    assert client.post('/profile/personality-quiz',headers=attendee,json={'answers':[0,0,0]}).status_code==200
    assert client.get('/v2/profile',headers=attendee).json()['completion']['score']==40
    assert client.get(f'/events/{event}/quiz',headers=attendee).status_code==404
    assert client.get('/quiz-templates',headers=owner).status_code==404


def test_profile_requires_quiz_for_full_score(client):
    token=client.post('/auth/signup',json={'name':'Full','email':'full@example.com','password':'testpassword'}).json()['token']
    auth={'Authorization':'Bearer '+token}
    complete_basic(client,auth)
    fields={key:'Filled' for key in ('headline','role','organization','skills','expertise','industry','projects','experience','achievements','website','additional_social','networking_goals')}
    fields['phone']='+1234567890'
    assert client.put('/v2/profile',headers=auth,json=fields).status_code==200
    assert client.get('/v2/profile',headers=auth).json()['completion']['score']==85
    assert client.post('/profile/personality-quiz',headers=auth,json={'answers':[0,0,0]}).status_code==200
    progress=client.get('/v2/profile',headers=auth).json()['completion']
    assert progress['score']==100 and progress['complete']
    assert client.put('/v2/profile',headers=auth,json=fields).status_code==200
    assert client.get('/v2/profile',headers=auth).json()['completion']['score']==100


def test_enrichment_requires_consent_review_and_preserves_sources(client, monkeypatch):
    import enrichment
    def fake_preview(url):
        return ({'bio': 'A' * 100, 'interests':'AI, design', 'headline':'Designer'}, {'model':'test'})
    monkeypatch.setattr(enrichment, 'preview', fake_preview)
    def signup(name):
        token = client.post('/auth/signup',json={'name':name,'email':name+'@example.com','password':'testpassword'}).json()['token']
        return {'Authorization':'Bearer '+token}
    user, other = signup('person'), signup('other')
    assert client.post('/v2/profile/enrichment/preview',headers=user,json={'url':'https://example.com/me','consent':False}).status_code == 403
    assert client.post('/v2/profile/enrichment/preview',headers=user,json={'url':'http://localhost/admin','consent':True}).status_code == 422
    response=client.post('/v2/profile/enrichment/preview',headers=user,json={'url':'https://example.com/me','consent':True})
    assert response.status_code==200, response.text
    draft=response.json()
    assert client.get('/me',headers=user).json()['bio']==''
    payload={'draft_token':draft['draft_token'],'fields':{'headline':'Edited designer','bio':'A'*100}}
    assert client.post('/v2/profile/enrichment/apply',headers=other,json=payload).status_code==400
    assert client.post('/v2/profile/enrichment/apply',headers=user,json={'draft_token':draft['draft_token'],'fields':{'phone':'1234567'}}).status_code==422
    assert client.post('/v2/profile/enrichment/apply',headers=user,json=payload).status_code==200
    assert client.get('/me',headers=user).json()['bio']=='A'*100
    profile=client.get('/v2/profile',headers=user).json()
    assert profile['headline']=='Edited designer' and profile['enrichment_sources']['headline']['user_edited']
    assert profile['enrichment_sources']['bio']['url']=='https://example.com/me'
    assert client.post('/v2/profile/enrichment/apply',headers=user,json=payload).status_code==409
    client.put('/v2/profile',headers=user,json={'headline':'Manually changed'})
    assert 'headline' not in client.get('/v2/profile',headers=user).json()['enrichment_sources']


def test_exa_preview_uses_only_approved_url(monkeypatch):
    import io, json, enrichment
    monkeypatch.setenv('EXA_API_KEY','test-exa')
    monkeypatch.setenv('OPENAI_API_KEY','test-openai')
    def fake_urlopen(req, timeout):
        assert req.full_url=='https://api.exa.ai/contents'
        assert json.loads(req.data)['urls']==['https://example.com/person']
        return io.BytesIO(json.dumps({'results':[{'url':'https://example.com/person','text':'A public profile'}]}).encode())
    monkeypatch.setattr(enrichment.urllib.request,'urlopen',fake_urlopen)
    def fake_generate(schema,instructions,data):
        assert data['page_text']=='A public profile'
        return schema(**{key:('Artist' if key=='headline' else '') for key in schema.model_fields}), {'model':'test'}
    monkeypatch.setattr(enrichment,'generate',fake_generate)
    assert enrichment.preview('https://example.com/person')[0]['headline']=='Artist'


def test_enrichment_unavailable_and_mismatched_source(monkeypatch):
    import io, json, enrichment
    monkeypatch.delenv('EXA_API_KEY', raising=False)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    with pytest.raises(RuntimeError, match='Exa API key'):
        enrichment.preview('https://example.com/person')
    monkeypatch.setenv('EXA_API_KEY','test-exa')
    monkeypatch.setenv('OPENAI_API_KEY','test-openai')
    monkeypatch.setattr(enrichment.urllib.request,'urlopen',lambda req, timeout: io.BytesIO(json.dumps({'results':[{'url':'https://example.com/other','text':'Wrong profile'}]}).encode()))
    with pytest.raises(RuntimeError, match='did not match'):
        enrichment.preview('https://example.com/person')
def _eligible_room(client, name='world-user'):
    token=client.post('/auth/signup',json={'name':name,'email':f'{name}@example.com','password':'testpassword'}).json()['token']
    auth={'Authorization':'Bearer '+token}
    start=datetime.now(timezone.utc)+timedelta(days=1)
    event=client.post('/events',headers=auth,json={'title':'World test','description':'A test event','starts_at':start.isoformat(),'ends_at':(start+timedelta(hours=1)).isoformat(),'published':True}).json()['id']
    complete_basic(client,auth)
    client.post(f'/events/{event}/register',headers=auth)
    return event,token


def test_world_config_endpoint_and_authoritative_geometry(client):
    import world
    response=client.get('/worlds')
    assert response.status_code==200
    data=response.json()
    assert data['revision']=='worlds-v1'
    assert {r['id'] for r in data['rooms']}=={'plaza','cafe','garden','arcade','lab'}
    assert client.get('/worlds/not-a-world').status_code==404
    thin_wall={'id':'thin','shape':'aabb','x':500,'y':100,'width':32,'height':800}
    room={'bounds':{'x':0,'y':0,'width':1000,'height':1000},'colliders':[thin_wall]}
    x,y=world.swept_move(room,(200,500),(800,500))
    assert x<=472 and y==500
    assert world.CHAT_RADIUS==280


def test_spatial_portal_uses_server_destination_and_spawn(client, monkeypatch):
    import time
    monkeypatch.setenv('WORLD_ALLOW_ROOM_SWITCH','1')
    event,token=_eligible_room(client,'portal-user')
    with client.websocket_connect(f'/ws/events/{event}?token={token}') as ws:
        presence=ws.receive_json()
        assert presence['world_revision']=='worlds-v1'
        person=presence['participants'][0]
        assert (person['x'],person['y'])==(960,884)
        ws.send_json({'type':'room','room_id':'lab'})
        changed=ws.receive_json()
        assert changed['room_id']=='lab' and changed['spawn_id']=='default'
        ws.receive_json()  # room-scoped presence after the debug-only transition
        time.sleep(.5)
        ws.send_json({'type':'move','seq':1,'x':1530,'y':860,'direction':'down','walking':True})
        assert ws.receive_json()['type']=='position'
        ws.receive_json()  # room-scoped presence
        ws.send_json({'type':'portal_enter','portal_id':'lab_to_plaza'})
        changed=ws.receive_json()
        assert changed['type']=='room_changed'
        assert changed['room_id']=='plaza' and changed['spawn_id']=='from_lab'
        assert (changed['x'],changed['y'])==(1450,820)


def test_production_socket_rejects_room_tabs_and_remote_movement(client, monkeypatch):
    monkeypatch.delenv('WORLD_ALLOW_ROOM_SWITCH',raising=False)
    event,token=_eligible_room(client,'secure-room-user')
    with client.websocket_connect(f'/ws/events/{event}?token={token}') as ws:
        ws.receive_json()
        ws.send_json({'type':'room','room_id':'garden'})
        switch_error=ws.receive_json()
        assert switch_error['type']=='world_error' and switch_error['code']=='room_switch_disabled'
        ws.send_json({'type':'portal_enter','portal_id':'garden_to_plaza'})
        error=ws.receive_json()
        assert error['type']=='world_error' and error['code']=='portal_out_of_range'
        ws.send_json({'type':'move','seq':6,'x':1100,'y':884,'direction':'right','walking':True})
        too_fast=ws.receive_json()
        assert too_fast['type']=='position' and too_fast['accepted'] is False
        ws.receive_json()  # unchanged presence
        ws.send_json({'type':'move','seq':7,'x':float('nan'),'y':884,'direction':'up','walking':True})
        invalid=ws.receive_json()
        assert invalid['type']=='position' and invalid['accepted'] is False
        ws.send_json({'type':'move','seq':8,'x':9000,'y':9000,'direction':'up','walking':True})
        position=ws.receive_json()
        assert position['type']=='position' and position['accepted'] is False
        assert (position['x'],position['y'])==(960,884)
        ws.receive_json()  # unchanged presence snapshot
        ws.send_json({'type':'move','seq':8,'x':960,'y':884,'direction':'up','walking':False})
        replay=ws.receive_json()
        assert replay['type']=='position' and replay['accepted'] is False


def test_move_socket_rate_limit_is_twenty_per_second():
    from collections import deque
    from main import allow_move_request
    timestamps=deque()
    assert all(allow_move_request(timestamps, 0.01*i) for i in range(20))
    assert not allow_move_request(timestamps, .2)
    assert allow_move_request(timestamps, 1.01)


def test_valid_diagonal_movement_is_accepted(client):
    import time
    event,token=_eligible_room(client,'diagonal-move-user')
    with client.websocket_connect(f'/ws/events/{event}?token={token}') as ws:
        ws.receive_json()
        time.sleep(.1)
        ws.send_json({'type':'move','seq':1,'x':970,'y':894,'direction':'down','walking':True})
        position=ws.receive_json()
        assert position['type']=='position' and position['accepted'] is True
        assert (position['x'],position['y'])==(970,894)


def test_world_reachability_seats_and_garden_bridges(client):
    import world
    garden=world.ROOMS['garden']
    west=next(p for p in garden['walkablePolygons'] if p['id']=='west-bridge')
    south=next(p for p in garden['walkablePolygons'] if p['id']=='south-bridge')
    assert min(x for x,_ in west['points']) <= 640 and max(x for x,_ in west['points'])-min(x for x,_ in west['points']) >= 180
    assert max(x for x,_ in south['points'])-min(x for x,_ in south['points']) >= 180
    assert world.swept_move(garden,(820,400),(820,640))==(820.0,640.0)
    assert world.swept_move(garden,(840,800),(1100,800))==(1100.0,800.0)
    for x,y in ((630,520),(1020,520),(1030,640),(900,910)):
        assert world.blocked(garden,x,y), (x,y)
    for room in world.ROOMS.values():
        assert all({'id','x','y','facing'} <= seat.keys() for seat in room['seats'])
        assert len({seat['id'] for seat in room['seats']})==len(room['seats'])


def test_each_portal_has_a_reachable_threshold_and_safe_named_spawn(client):
    import world
    for room in world.ROOMS.values():
        entry=next(s for s in room['spawns'] if s['id'] in ('default','from_plaza'))
        reachable=world._reachable_grid(room,(entry['x'],entry['y']))
        for portal in room['portals']:
            assert world._grid_reaches_shape(reachable,portal['trigger']), (room['id'],portal['id'])
            dest=portal['destination']; destination=world.ROOMS[dest['roomId']]
            spawn=world.safe_spawn(destination,dest['spawnId'])
            assert spawn['id']==dest['spawnId'] and not world.blocked(destination,spawn['x'],spawn['y'])


def test_original_room_specs_fail_reachability_validation(client):
    import json
    import world
    original=json.loads((__import__('pathlib').Path(__file__).parent/'fixtures'/'room-specs-original.json').read_text(encoding='utf-8'))
    rooms={room['id']:room for room in original['rooms']}
    plaza=rooms['plaza']
    spawn=next(s for s in plaza['spawns'] if s['id']=='default')
    reachable=world._reachable_grid(plaza,(spawn['x'],spawn['y']))
    cafe_portal=next(p for p in plaza['portals'] if p['id']=='plaza_to_cafe')
    assert not world._grid_reaches_shape(reachable,cafe_portal['trigger'])
    for room in world.ROOMS.values():
        entry=next(s for s in room['spawns'] if s['id'] in ('default','from_plaza'))
        reachable=world._reachable_grid(room,(entry['x'],entry['y']))
        assert all(world._grid_reaches_shape(reachable,p['trigger']) for p in room['portals'])


def test_nearby_chat_remains_private_proximity_and_block_gated(client):
    event,alice_token=_eligible_room(client,'nearby-alice')
    bob_token=client.post('/auth/signup',json={'name':'nearby-bob','email':'nearby-bob@example.com','password':'testpassword'}).json()['token']
    bob_auth={'Authorization':'Bearer '+bob_token}
    complete_basic(client,bob_auth)
    client.post(f'/events/{event}/register',headers=bob_auth)
    alice_auth={'Authorization':'Bearer '+alice_token}
    bob_id=client.get('/me',headers=bob_auth).json()['id']
    from main import rooms
    with client.websocket_connect(f'/ws/events/{event}?token={alice_token}') as alice:
        alice.receive_json()
        with client.websocket_connect(f'/ws/events/{event}?token={bob_token}') as bob:
            alice.receive_json(); bob.receive_json()
            alice.send_json({'type':'chat','target_id':bob_id,'text':'Hello there'})
            assert alice.receive_json()['type']=='chat'
            assert bob.receive_json()['text']=='Hello there'
            bob_presence=next(p for p in rooms[event].values() if p['id']==bob_id)
            bob_presence['x']=1500
            alice.send_json({'type':'chat','target_id':bob_id,'text':'Too far'})
            assert alice.receive_json()['type']=='chat_error'
            bob_presence['x']=888
            assert client.post(f'/v2/blocks/{bob_id}',headers=alice_auth).status_code==200
            alice.send_json({'type':'chat','target_id':bob_id,'text':'Blocked'})
            error=alice.receive_json()
            assert error['type']=='chat_error' and error['message']=='Participant unavailable.'
            alice.send_json({'type':'move','seq':1,'x':960,'y':884,'direction':'up','walking':False})
            alice.receive_json()  # accepted position
            snapshot=alice.receive_json()
            assert snapshot['type']=='presence' and all(p['id']!=bob_id for p in snapshot['participants'])
