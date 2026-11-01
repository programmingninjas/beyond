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


def test_profile_persona_and_consent(client):
    def signup(name):
        response = client.post('/auth/signup', json={'name': name, 'email': f'{name}@example.com', 'password': 'testpassword'})
        assert response.status_code == 200, response.text
        return {'Authorization': 'Bearer ' + response.json()['token']}
    a, b, c = signup('alice'), signup('bob'), signup('carol')
    start = datetime.now(timezone.utc) + timedelta(days=1)
    event = client.post('/events', headers=a, json={'title':'Test', 'starts_at':start.isoformat(), 'ends_at':(start+timedelta(hours=2)).isoformat(), 'published':True}).json()['id']
    for headers in (a, b, c):
        assert client.post(f'/events/{event}/register', headers=headers).status_code == 200
        assert client.post(f'/events/{event}/quiz/submit', headers=headers, json={'answers':[0,0,0]}).status_code == 200
    assert client.put('/v2/profile', headers=a, json={'headline':'Founder','avatar':'axolotl'}).status_code == 200
    assert client.get('/v2/profile', headers=a).json()['headline'] == 'Founder'
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
    assert all(p['id'] != bob_id for p in client.get(f'/events/{event}/recommendations', headers=a).json())
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
        assert conn.execute(text('SELECT count(*) FROM schema_versions')).scalar_one() == 2


def test_matching_and_conversation_are_cached_and_authorized(client, monkeypatch):
    import networking
    import time
    from ai_service import Match, PetConversation
    calls = []
    def fake_generate(kind, instructions, data):
        calls.append((kind.__name__, data))
        if kind is Match:
            return Match(circle='shared', scores=[80,90,70,80,60], evidence=['Shared AI interest'], explanation='They can collaborate.', conversation_starter='What are you building?'), {'model':'test','usage':{}}
        return PetConversation(messages=[{'speaker':'requester' if i % 2 == 0 else 'recipient','phase':'discovery','text':'Hello'} for i in range(4)], highlights=['Shared AI interest'], summary='They may collaborate.', outcome='potential'), {'model':'test','usage':{}}
    monkeypatch.setattr(networking, 'generate', fake_generate)
    def signup(name):
        return {'Authorization': 'Bearer ' + client.post('/auth/signup',json={'name':name,'email':f'{name}@example.com','password':'testpassword'}).json()['token']}
    a,b,c=signup('alice'),signup('bob'),signup('carol')
    start=datetime.now(timezone.utc)+timedelta(days=1)
    event=client.post('/events',headers=a,json={'title':'Test','starts_at':start.isoformat(),'ends_at':(start+timedelta(hours=1)).isoformat(),'published':True}).json()['id']
    for h in (a,b):
        client.post(f'/events/{event}/register',headers=h); client.post(f'/events/{event}/quiz/submit',headers=h,json={'answers':[0,0,0]})
    bob=client.get('/me',headers=b).json()['id']
    client.put(f'/v2/events/{event}/persona',headers=a,json={'seeking':'A designer','offering':'Secret offer'})
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
    monkeypatch.setenv('WORLD_DEBUG_ROOM_TABS', '1')
    token=client.post('/auth/signup',json={'name':'alex','email':'alex@example.com','password':'testpassword'}).json()['token']
    auth={'Authorization':'Bearer '+token}
    start=datetime.now(timezone.utc)+timedelta(days=1)
    event=client.post('/events',headers=auth,json={'title':'Test','starts_at':start.isoformat(),'ends_at':(start+timedelta(hours=1)).isoformat(),'published':True}).json()['id']
    client.post(f'/events/{event}/register',headers=auth)
    client.post(f'/events/{event}/quiz/submit',headers=auth,json={'answers':[0,0,0]})
    with client.websocket_connect(f'/ws/events/{event}?token={token}') as ws:
        assert ws.receive_json()['participants'][0]['room_id']=='plaza'
        ws.send_json({'type':'room','room_id':'garden'})
        assert ws.receive_json()['room_id']=='garden'
        assert ws.receive_json()['participants'][0]['room_id']=='garden'


def _eligible_room(client, name='world-user'):
    token=client.post('/auth/signup',json={'name':name,'email':f'{name}@example.com','password':'testpassword'}).json()['token']
    auth={'Authorization':'Bearer '+token}
    start=datetime.now(timezone.utc)+timedelta(days=1)
    event=client.post('/events',headers=auth,json={'title':'World test','description':'A test event','starts_at':start.isoformat(),'ends_at':(start+timedelta(hours=1)).isoformat(),'published':True}).json()['id']
    client.post(f'/events/{event}/register',headers=auth)
    client.post(f'/events/{event}/quiz/submit',headers=auth,json={'answers':[0,0,0]})
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
    monkeypatch.setenv('WORLD_DEBUG_ROOM_TABS','1')
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
    monkeypatch.delenv('WORLD_DEBUG_ROOM_TABS',raising=False)
    event,token=_eligible_room(client,'secure-room-user')
    with client.websocket_connect(f'/ws/events/{event}?token={token}') as ws:
        ws.receive_json()
        ws.send_json({'type':'room','room_id':'garden'})
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


def test_nearby_chat_remains_private_proximity_and_block_gated(client):
    event,alice_token=_eligible_room(client,'nearby-alice')
    bob_token=client.post('/auth/signup',json={'name':'nearby-bob','email':'nearby-bob@example.com','password':'testpassword'}).json()['token']
    bob_auth={'Authorization':'Bearer '+bob_token}
    client.post(f'/events/{event}/register',headers=bob_auth)
    client.post(f'/events/{event}/quiz/submit',headers=bob_auth,json={'answers':[0,0,0]})
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
