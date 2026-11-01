"""Create a labelled fictional demo, without calling OpenAI. Run inside the API container."""
from datetime import timedelta
from networking import circle_for_score
from main import (startup, SessionLocal, User, Event, Registration, V2Profile, V2Persona,
                  V2Recommendation, V2Introduction, V2Transcript, V2Job, passwords, now, TEMPLATE)


def main():
    startup()
    with SessionLocal() as db:
        if db.query(Event).filter_by(title='Fictional Demo: Meet Beyond').first():
            print('Demo already exists.'); return
        attendees = [
            ('demo.alex@example.com','Alex Rivera','AI founder','AI education, agentic systems','I am building an AI education platform.','A developer interested in education','Product direction and education contacts'),
            ('demo.devon@example.com','Devon Lee','AI developer','AI education, agentic systems','I develop agentic products.','Early-stage startup collaborations','AI engineering'),
            ('demo.sam@example.com','Sam Patel','AI engineer','agentic systems, machine learning','I build AI assistants.','Technical peers','Machine learning experience'),
            ('demo.jules@example.com','Jules Park','Game designer','behavior change, education','I design engaging learning experiences.','Education researchers','Game design'),
            ('demo.morgan@example.com','Morgan Chen','Educator','student engagement, education','I study student engagement.','Game designers','Education research'),
            ('demo.taylor@example.com','Taylor Stone','Accountant','tax, bookkeeping','I work on tax compliance.','Accounting peers','Accounting')]
        users=[]
        for email,name,headline,interests,attending,seeking,offering in attendees:
            if db.query(User).filter_by(email=email).first(): raise RuntimeError('Demo email already exists; use a clean database')
            u=User(email=email,name=name,password=passwords.hash('BeyondDemo2026!'),bio=attending,interests=interests,profile_url='',enrichment_consent=False);db.add(u);db.flush();users.append(u)
            db.add(V2Profile(user_id=u.id,discoverable=True,data={'headline':headline,'role':headline,'avatar':'red-panda','pet_name':'Spark','pet_color':'#c4b5fd','pet_style':'curious'}))
        event=Event(owner_id=users[0].id,title='Fictional Demo: Meet Beyond',description='Fictional sample attendees and precomputed example results; no live AI generation.',category='Demo',location='Online',starts_at=now()+timedelta(days=30),ends_at=now()+timedelta(days=30,hours=3),published=True,quiz=TEMPLATE);db.add(event);db.flush()
        for u, data in zip(users,attendees):
            db.add(Registration(event_id=event.id,user_id=u.id,personality='Explorer'))
            db.add(V2Persona(event_id=event.id,user_id=u.id,data={'attending':data[4],'seeking':data[5],'offering':data[6],'projects':'','topics':data[3]}))
        for index,score,reason in [(1,88,'Alex needs AI development; Devon offers AI engineering and seeks startup collaboration.'),(2,80,'Both work on agentic AI systems.'),(3,58,'Education and game design both relate to engagement.'),(4,65,'Education research could inform an AI learning product.'),(5,20,'Their profiles provide limited evidence of a shared networking goal.')]:
            circle=circle_for_score(score)
            db.add(V2Recommendation(event_id=event.id,user_id=users[0].id,candidate_id=users[index].id,data={'circle':circle,'score':score,'scores':[score]*5,'evidence':[reason],'explanation':reason,'conversation_starter':'What are you working on?','model':'fictional-precomputed-demo','usage':{}}))
        intro=V2Introduction(event_id=event.id,requester_id=users[0].id,recipient_id=users[1].id,state='approved',requester_sharing=['name','seeking','offering'],recipient_sharing=['name','seeking','offering']);db.add(intro);db.flush()
        messages=[{'speaker':'requester','phase':'introduction','text':'Alex is looking for a developer for an AI education product.'},{'speaker':'recipient','phase':'discovery','text':'Devon offers AI engineering and is looking for a startup collaboration.'},{'speaker':'requester','phase':'spark','text':'That sounds like a practical fit for Alex’s project.'},{'speaker':'recipient','phase':'conclusion','text':'They could discuss the product and whether they want to work together.'}]
        db.add(V2Transcript(introduction_id=intro.id,data={'messages':messages,'highlights':['AI engineering meets an education startup'], 'summary':'Alex is seeking development help, and Devon offers AI engineering and wants startup collaboration.', 'outcome':'strong','model':'fictional-precomputed-demo','usage':{}},requester_decision='pending',recipient_decision='pending'))
        db.add(V2Job(kind='matching',event_id=event.id,user_id=users[0].id,target_id=0,state='complete',error=''))
        db.commit();print('Fictional demo created. Sign in as demo.alex@example.com or demo.devon@example.com with password BeyondDemo2026!')

if __name__=='__main__': main()
