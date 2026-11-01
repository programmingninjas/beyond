'use client';
import {useEffect, useRef, useState} from 'react';

const API = process.env.NEXT_PUBLIC_API_URL || (typeof window !== 'undefined' ? `${window.location.protocol}//${window.location.hostname}:8000` : 'http://localhost:8000');
const profileFields = [['phone','Phone number'],['projects','Projects'],['experience','Experience'],['achievements','Achievements'],['website','Personal website'],['additional_social','Additional social links'],['networking_goals','Networking goals'],['headline','Professional headline'],['role','Current role'],['organization','Organization or school'],['skills','Skills'],['expertise','Areas of expertise'],['industry','Industry']];
const personaFields = [['attending','Why are you attending?'],['seeking','What are you looking for?'],['offering','What can you offer?'],['projects','Current projects'],['topics','Topics to discuss']];
const shareFields = ['name','bio','interests','headline','role','organization','skills','expertise','industry','attending','seeking','offering','projects','topics'];

export function V2Panel({token, mode, eventId}: {token:string; mode:'profile'|'persona'|'introductions'; eventId?:number}) {
 const [data,setData]=useState<any>({}); const [items,setItems]=useState<any[]>([]); const [message,setMessage]=useState(''); const [error,setError]=useState(''); const [sharing,setSharing]=useState<string[]>(['name']); const [savedSharing,setSavedSharing]=useState<string[]>(['name']);
 const path=mode==='profile'?'/v2/profile':mode==='persona'?`/v2/events/${eventId}/persona`:'/v2/introductions';
 async function call(url:string, options:RequestInit={}) {const r=await fetch(API+url,{...options,headers:{'Content-Type':'application/json',Authorization:`Bearer ${token}`}});const json=await r.json();if(!r.ok)throw new Error(json.detail||'Unable to complete request');return json}
 async function load(){try{const result=await call(path);if(mode==='introductions')setItems(result);else setData(result);setError('')}catch(e:any){setError(e.message)}}
 useEffect(()=>{load();if(mode==='introductions')call('/v2/profile/pet-sharing').then(prefs=>{setSharing(prefs.fields);setSavedSharing(prefs.fields)}).catch((e:any)=>setError(e.message));const changed=()=>load();window.addEventListener('beyond-profile-changed',changed);const timer=mode==='introductions'?setInterval(load,5000):undefined;return()=>{window.removeEventListener('beyond-profile-changed',changed);if(timer)clearInterval(timer)}},[token,mode,eventId]);
 async function save(e:React.FormEvent){e.preventDefault();try{await call(path,{method:'PUT',body:JSON.stringify(data)});await load();setMessage('Saved.');setError('')}catch(e:any){setError(e.message)}}
 async function decision(id:number, action:string){try{const result=await call(`/v2/introductions/${id}/${action}`,{method:'POST',body:JSON.stringify({fields:sharing})});setMessage(result.message||'Decision saved.');await load()}catch(e:any){setError(e.message)}}
 if(mode==='introductions')return <div className="panel stack"><h2>Pet sharing settings</h2><p>Choose the profile details your pet is allowed to share when requesting or approving an introduction. These preferences are saved to your account. You can update them at any time.</p>{error&&<div className="alert">{error}</div>}{message&&<div className="notice">{message}</div>}<fieldset><legend>My pet may share</legend>{shareFields.map(field=><label className="checkbox" key={field}><input type="checkbox" checked={sharing.includes(field)} onChange={e=>setSharing(e.target.checked?[...sharing,field]:sharing.filter(x=>x!==field))}/>{field.replaceAll('_',' ')}</label>)}</fieldset><button className="button primary" disabled={sharing.length===savedSharing.length&&sharing.every(x=>savedSharing.includes(x))} onClick={async()=>{try{const result=await call('/v2/profile/pet-sharing',{method:'PUT',body:JSON.stringify({fields:sharing})});setSharing(result.fields);setSavedSharing(result.fields);setMessage('Pet sharing preferences saved.');setError('')}catch(e:any){setError(e.message)}}}>Save sharing preferences</button><section className="stack"><h3>Introduction requests</h3>{items.map(item=><div className="panel stack" key={item.id}><b>{item.other}</b><span>{item.incoming?'Incoming request':'Your request'} · {item.state}</span>{item.incoming&&item.state==='pending'&&<><p>Your saved sharing preferences will be shared if you approve.</p><button className="button primary" onClick={()=>decision(item.id,'approve')}>Approve introduction</button><button className="button outline" onClick={()=>decision(item.id,'decline')}>Decline</button></>}{item.state==='approved'&&<Conversation token={token} introId={item.id}/>}</div>)}{!items.length&&<p className="muted">No introduction requests yet. Your saved settings will apply the next time you send or receive a request.</p>}</section></div>;
 const fields=mode==='profile'?profileFields:personaFields;
 return <form className="panel stack" onSubmit={save}><h2>{mode==='profile'?'Your networking identity':'Your event persona'}</h2>{mode==='profile'&&data.enrichment_sources&&Object.keys(data.enrichment_sources).length>0&&<details><summary>Imported field sources</summary>{Object.entries(data.enrichment_sources).map(([field,source]:[string,any])=><p key={field}>{field}: <a href={source.url} target="_blank" rel="noreferrer">{source.url}</a>{source.user_edited?' (edited before saving)':''}</p>)}</details>}{mode==='profile'&&data.completion&&<div><b>Profile {data.completion.score}% complete</b><p>{data.completion.basic_complete?'Basic profile complete.':`Required for registration: ${data.completion.missing_basic.join(', ')}`}</p>{data.completion.complete&&<strong>Complete profile ✓</strong>}</div>}{error&&<div className="alert">{error}</div>}{message&&<div className="notice">{message}</div>}{fields.map(([key,label])=><label key={key}>{label}<input value={data[key]||''} onChange={e=>setData({...data,[key]:e.target.value})}/></label>)}{mode==='profile'&&<><label>Animal avatar<select value={data.avatar||'red-panda'} onChange={e=>setData({...data,avatar:e.target.value})}><option value="red-panda">Red panda</option><option value="axolotl">Axolotl</option><option value="sunda-pangolin">Sunda pangolin</option><option value="kakapo">Kākāpō</option><option value="vaquita">Vaquita</option></select></label><label>Pet name<input value={data.pet_name||''} onChange={e=>setData({...data,pet_name:e.target.value})}/></label><label>Pet color<input type="color" value={data.pet_color||'#c4b5fd'} onChange={e=>setData({...data,pet_color:e.target.value})}/></label><label>Pet style<select value={data.pet_style||'curious'} onChange={e=>setData({...data,pet_style:e.target.value})}>{['curious','playful','calm','energetic'].map(s=><option key={s}>{s}</option>)}</select></label><label className="checkbox"><input type="checkbox" checked={data.discoverable!==false} onChange={e=>setData({...data,discoverable:e.target.checked})}/>Appear in discovery</label></>}<button className="button primary">Save {mode==='profile'?'networking profile':'event persona'}</button></form>
}

export function PetRequest({token,eventId,personId}:{token:string;eventId:number;personId:number}) {
 const [fields,setFields]=useState<string[]>(['name']); const [status,setStatus]=useState(''); const [busy,setBusy]=useState(false);
 useEffect(()=>{fetch(`${API}/v2/profile/pet-sharing`,{headers:{Authorization:`Bearer ${token}`}}).then(r=>r.json()).then(d=>setFields(d.fields||['name'])).catch(()=>{})},[token]);
 async function send(){setBusy(true);try{const r=await fetch(`${API}/v2/events/${eventId}/introductions/${personId}`,{method:'POST',headers:{'Content-Type':'application/json',Authorization:`Bearer ${token}`},body:JSON.stringify({fields})});const body=await r.json();if(!r.ok)throw new Error(body.detail||'Request failed');setStatus('Introduction request sent.');}catch(e:any){setStatus(e.message)}finally{setBusy(false)}}
 return <div>{status&&<p className="small">{status}</p>}<p className="small muted">Your pet will share: {fields.map(x=>x.replaceAll('_',' ')).join(', ')||'no profile details'}</p><button className="button outline wide" disabled={busy} onClick={send}>{busy?'Sending…':'Request pet introduction ↗'}</button></div>
}

export function Discovery({token,eventId}:{token:string;eventId:number}) {
 const [data,setData]=useState<any>({matches:[],job:null}); const [directory,setDirectory]=useState<any[]>([]); const [error,setError]=useState('');
 async function call(path:string, options:RequestInit={}){const r=await fetch(API+path,{...options,headers:{'Content-Type':'application/json',Authorization:`Bearer ${token}`}});const body=await r.json();if(!r.ok)throw new Error(body.detail||'Request failed');return body}
 async function load(){try{const [matches,people]=await Promise.all([call(`/v2/events/${eventId}/matching`),call(`/v2/events/${eventId}/directory`)]);setData(matches);setDirectory(people)}catch(e:any){setError(e.message)}}
 useEffect(()=>{load();const changed=()=>load();window.addEventListener('beyond-data-changed',changed);return()=>window.removeEventListener('beyond-data-changed',changed)},[token,eventId]);
 useEffect(()=>{if(!['pending','running'].includes(data.job?.state))return;const timer=setInterval(load,4000);return()=>clearInterval(timer)},[data.job?.state,token,eventId]);
 const sections=[['inner','Inner Circle','First degree · compatibility above 80%'],['shared','Shared Universe','Second degree · compatibility above 60% and up to 80%'],['perspectives','New Perspectives','Third degree · compatibility above 40% and up to 60%'],['serendipity','Serendipity Circle','Fourth degree · compatibility up to 40%']];
 return <div className="stack"><div className="panel stack"><h2>Your networking circles</h2><p>Discover why you might want to meet. Rankings are generated in the background and saved for this event.</p><button className="button primary" disabled={['pending','running'].includes(data.job?.state)} onClick={async()=>{try{await call(`/v2/events/${eventId}/matching/refresh`,{method:'POST'});await load()}catch(e:any){setError(e.message)}}}>Refresh recommendations</button>{data.job&&<p>Matching: {data.job.state}{data.job.error&&` — ${data.job.error}`}</p>}{!data.job&&<p>Choose refresh to generate your recommendations.</p>}{error&&<p className="alert">{error}</p>}</div>{sections.map(([key,title,description],i)=>{const matches=data.matches.filter((m:any)=>m.circle===key);return <section key={key}><h2>{String(i+1).padStart(2,'0')} — {title} <small>({matches.length})</small></h2><p>{description}</p><div className="people-grid">{matches.map((m:any)=><div className="panel stack" key={m.id}><div className="person-avatar">✦</div><h3>{m.name}</h3><strong>{m.score}% relevance</strong>{m.model==='fictional-precomputed-demo'&&<small>Fictional precomputed demo</small>}<p>{m.explanation}</p><p>{m.conversation_starter}</p><details><summary>Supporting evidence</summary><ul>{m.evidence.map((e:string)=><li key={e}>{e}</li>)}</ul></details><PetRequest token={token} eventId={eventId} personId={m.id}/></div>)}</div>{!matches.length&&<p className="muted">No recommendations in this circle yet.</p>}</section>})}<section><h2>Attendee directory</h2><div className="people-grid">{directory.map(p=><div className="panel stack" key={p.id}><h3>{p.name}</h3><p>{p.bio}</p><PetRequest token={token} eventId={eventId} personId={p.id}/></div>)}</div>{!directory.length&&<p>No other eligible attendees yet.</p>}</section></div>
}

const avatarSpecies:Record<string,string>={'red-panda':'Red panda',axolotl:'Axolotl','sunda-pangolin':'Sunda pangolin',kakapo:'Kākāpō',vaquita:'Vaquita'};
const petDefaults={pet_name:'Spark',pet_color:'#c4b5fd',pet_style:'curious',avatar:'red-panda',owner_name:'Your match'};
function petTint(hex:string){const safe=/^#[\da-f]{6}$/i.test(hex)?hex:'#c4b5fd';const n=parseInt(safe.slice(1),16);const mix=(shift:number)=>Math.round(((n>>shift)&255)*.14+255*.86).toString(16).padStart(2,'0');return `#${mix(16)}${mix(8)}${mix(0)}`}
function petForeground(hex:string){const n=parseInt(hex.replace('#',''),16);const r=n>>16,g=(n>>8)&255,b=n&255;return (r*299+g*587+b*114)/1000>155?'#24352b':'#ffffff'}
function titleCase(value:string){return value.replace(/[-_]+/g,' ').replace(/\b\w/g,char=>char.toUpperCase())}

export function Conversation({token,introId}:{token:string;introId:number}) {
 const [data,setData]=useState<any>({});
 const [error,setError]=useState('');
 const [loading,setLoading]=useState(true);
 const [visibleCount,setVisibleCount]=useState(0);
 const [playing,setPlaying]=useState(false);
 const [busy,setBusy]=useState(false);
 const [connected,setConnected]=useState(false);
 const threadRef=useRef<HTMLDivElement>(null);
 async function call(suffix:string,options:RequestInit={}){
  let response:Response;
  try{response=await fetch(`${API}/v2/introductions/${introId}/${suffix}`,{...options,headers:{'Content-Type':'application/json',Authorization:`Bearer ${token}`}})}
  catch{throw new Error('unreachable')}
  const result=await response.json().catch(()=>({}));
  if(!response.ok)throw new Error('request-failed');
  return result;
 }
 async function load(){
  try{const result=await call('conversation');setData(result);setError('')}
  catch{setError("Couldn't reach the server. Retrying…")}
  finally{setLoading(false)}
 }
 useEffect(()=>{setLoading(true);void load();const timer=setInterval(()=>void load(),4000);return()=>clearInterval(timer)},[introId,token]);
 const convo=data.conversation;
 const messages:any[]=convo?.messages||[];
 const total=messages.length;
 const visibleMessages=messages.slice(0,visibleCount);
 const viewerSide=data.pets?.viewer_side==='recipient'?'recipient':'requester';
 const otherSide=viewerSide==='requester'?'recipient':'requester';
 const myPet={...petDefaults,...(data.pets?.[viewerSide]||{})};
 const theirPet={...petDefaults,...(data.pets?.[otherSide]||{})};
 const currentSpeaker=playing&&visibleCount<total?messages[visibleCount]?.speaker:visibleMessages[visibleMessages.length-1]?.speaker;
 const activeSide=currentSpeaker===viewerSide?'mine':currentSpeaker?'theirs':'';
 useEffect(()=>{if(convo&&total>0&&visibleCount===0&&!playing)setVisibleCount(1)},[convo?.model,total]);
 useEffect(()=>{
  if(!playing||visibleCount>=total){if(visibleCount>=total)setPlaying(false);return}
  const timer=setTimeout(()=>setVisibleCount(count=>Math.min(count+1,total)),visibleCount===0?550:1450);
  return()=>clearTimeout(timer);
 },[playing,visibleCount,total]);
 useEffect(()=>{
  if(!visibleCount)return;
  const reduced=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  threadRef.current?.lastElementChild?.scrollIntoView({behavior:reduced?'auto':'smooth',block:'nearest'});
 },[visibleCount]);
 async function generate(){
  setBusy(true);
  try{await call('generate',{method:'POST'});setError('');await load()}
  catch{setError("Couldn't reach the server. Retrying…")}
  finally{setBusy(false)}
 }
 async function decide(action:string){
  setBusy(true);
  try{const result=await call('decision',{method:'POST',body:JSON.stringify({decision:action})});setConnected(result.connected);setError('');await load()}
  catch{setError("Couldn't reach the server. Retrying…")}
  finally{setBusy(false)}
 }
 const petCard=(pet:any,side:'mine'|'theirs',label:string)=>{
  const name=pet.pet_name||'Spark';const fill=/^#[\da-f]{6}$/i.test(pet.pet_color)?pet.pet_color:'#c4b5fd';
  return <section className={`conversation-pet-card ${activeSide===side?'speaking':''} ${activeSide&&activeSide!==side?'dimmed':''}`} aria-label={`${label}: ${name}, ${avatarSpecies[pet.avatar]||'Animal companion'}, ${titleCase(pet.pet_style||'curious')} style`}>
   <div className="conversation-pet-badge" style={{backgroundColor:fill,color:petForeground(fill)}} aria-hidden="true">{name.trim().charAt(0).toLocaleUpperCase()||'✦'}</div>
   <div className="conversation-pet-copy"><b>{name}</b><span>{avatarSpecies[pet.avatar]||'Animal companion'}</span><small>{titleCase(pet.pet_style||'curious')} · {label}</small></div>
  </section>
 };
 const retryPanel=<div className="conversation-error" role="alert"><div><b>{error||"Couldn't reach the server. Retrying…"}</b><span>Check your connection, then try again.</span></div><button className="button outline" onClick={()=>{setLoading(true);void load()}}>Retry</button></div>;
 if(loading&&!data.pets)return <section className="pet-conversation panel" aria-busy="true"><h3>Loading your pets’ conversation…</h3><div className="conversation-skeleton"/></section>;
 if(error&&!data.pets)return <section className="pet-conversation panel" aria-label="Pet conversation">{retryPanel}</section>;
 return <section className="pet-conversation panel stack" aria-label="Pet conversation">
  {error&&retryPanel}
  <header className="conversation-header">
   <div><p className="mini-label">A PRIVATE INTRODUCTION</p><h3>{myPet.pet_name||'Spark'} &amp; {theirPet.pet_name||'Spark'}</h3><p>A conversation between your pets, based only on what you each chose to share.</p></div>
  </header>
  <div className="pet-stage conversation-pet-pair" aria-label="Pets in this conversation">
   {petCard(myPet,'mine','Your pet')}
   <span className="conversation-pair-mark" aria-hidden="true">&amp;</span>
   {petCard(theirPet,'theirs',`${theirPet.owner_name||'Your match'}’s pet`)}
  </div>
  {!convo&&data.job?.state==='failed'&&<div className="conversation-state conversation-state-failed"><span className="conversation-state-icon" aria-hidden="true">↻</span><div><h4>Your pets couldn’t finish their conversation.</h4><p>Try generating it again. Nothing was lost.</p></div><button className="button primary" disabled={busy} onClick={generate}>Retry conversation</button></div>}
  {!convo&&['pending','running'].includes(data.job?.state)&&<div className="conversation-state" aria-live="polite"><div><h4>Your pets are talking…</h4><p>This can take a little while.</p></div><div className="pending-bubbles" aria-hidden="true"><span/><span/><span/></div></div>}
  {!convo&&!['pending','running','failed'].includes(data.job?.state)&&<div className="conversation-state conversation-state-ready"><div><h4>Ready when you are</h4><p>Both owners approved. Start the conversation to see what your pets share.</p></div><button className="button primary" disabled={busy} onClick={generate}>Generate conversation</button></div>}
  {convo&&<>
   <div className="conversation-toolbar" aria-label="Conversation playback controls">
    <div className="conversation-toolbar-buttons"><button className="button primary" onClick={()=>{if(!playing&&visibleCount>=total)setVisibleCount(0);setPlaying(value=>!value)}} disabled={!total}>{playing?'Pause':'Play'}<span aria-hidden="true">{playing?'Ⅱ':'▶'}</span></button><button className="button outline" onClick={()=>{setVisibleCount(0);setPlaying(true)}} disabled={!total}>Restart</button><button className="button outline" onClick={()=>{setPlaying(false);setVisibleCount(total)}} disabled={!total}>Show all</button></div>
    <div className="conversation-progress"><span>{Math.min(visibleCount,total)} of {total}</span><progress max={Math.max(total,1)} value={Math.min(visibleCount,total)} aria-label={`${Math.min(visibleCount,total)} of ${total} messages shown`}/></div>
   </div>
   <div className="conversation-thread" ref={threadRef} role="log" aria-label="Conversation thread" aria-live="polite" aria-relevant="additions text" aria-atomic="false">
    {visibleMessages.map((message:any,index:number)=>{
     const side=message.speaker===viewerSide?'mine':'theirs';const pet=side==='mine'?myPet:theirPet;const previous=visibleMessages[index-1];
     return <div key={`${index}-${message.phase}`}>
      {(!previous||previous.phase!==message.phase)&&<div className="conversation-phase"><span/>{titleCase(message.phase||'Conversation')}<span/></div>}
      <div className={`conversation-message-row ${side}`}>
       <article className="conversation-message" style={{'--message-tint':petTint(pet.pet_color)} as React.CSSProperties}><b>{pet.pet_name||'Spark'}</b><p>{message.text}</p></article>
      </div>
     </div>
    })}
    {playing&&visibleCount<total&&(()=>{const side=messages[visibleCount]?.speaker===viewerSide?'mine':'theirs';const pet=side==='mine'?myPet:theirPet;return <div className={`conversation-message-row ${side}`}><div className="conversation-typing" aria-label={`${pet.pet_name||'Pet'} is typing`}><i/><i/><i/></div></div>})()}
    {!total&&<p className="conversation-empty">The conversation is ready, but there are no messages to show.</p>}
   </div>
   <section className="conversation-discoveries"><div><p className="mini-label">SHARED THREADS</p><h4>Discoveries</h4></div><div className="discovery-cards">{(convo.highlights||[]).map((highlight:string,index:number)=><article className="discovery-card" key={`${highlight}-${index}`}><span aria-hidden="true">✦</span><p>{highlight}</p></article>)}</div></section>
   <section className="conversation-summary"><h4>Why might you meet?</h4><p>{convo.summary}</p></section>
   <section className="conversation-decision"><div><p className="mini-label">YOUR INTRODUCTION</p><h4>{connected?'You’re connected':`Your decision: ${titleCase(data.your_decision||'pending')}`}</h4><p>{connected?'You can continue the conversation in your connections.':'Accept to connect, decline to close this introduction, or withdraw your pending acceptance.'}</p></div><div className="conversation-decision-actions"><button className="button primary" disabled={busy||connected} onClick={()=>decide('accept')}>Accept introduction</button><button className="button outline" disabled={busy||connected} onClick={()=>decide('decline')}>Decline</button><button className="conversation-withdraw" disabled={busy||data.your_decision!=='accept'} onClick={()=>decide('withdraw')}>Withdraw acceptance</button></div></section>
  </>}
 </section>
}

export function PersonalityQuiz({token}:{token:string}) {
 const [quiz,setQuiz]=useState<any>(null);const [answers,setAnswers]=useState<number[]>([]);const [step,setStep]=useState(-1);const [result,setResult]=useState<any>(null);const [error,setError]=useState('');const [busy,setBusy]=useState(false);
 useEffect(()=>{fetch(API+'/profile/personality-quiz',{headers:{Authorization:`Bearer ${token}`}}).then(r=>{if(!r.ok)throw new Error();return r.json()}).then(q=>{setQuiz(q);setAnswers(q.questions.map(()=>-1))}).catch(()=>setError('Could not load quiz'))},[token]);
 const letters=['A','B','C','D'];
 async function finish(){setBusy(true);setError('');try{const r=await fetch(API+'/profile/personality-quiz',{method:'POST',headers:{'Content-Type':'application/json',Authorization:`Bearer ${token}`},body:JSON.stringify({answers})});const d=await r.json();if(!r.ok)throw new Error(d.detail||'Unable to save quiz');setResult(d);setStep(quiz.questions.length);window.dispatchEvent(new Event('beyond-profile-changed'))}catch(e:any){setError(e.message)}finally{setBusy(false)}}
 return <section className="personality-quiz" aria-label="Personality quiz"><div className="quiz-inner">{step<0?<div className="quiz-intro"><span className="quiz-kicker">A SEVEN QUESTION QUIZ</span><h2>Personality Quiz</h2><p>Discover your personality house through seven quick questions.</p><div className="quiz-personality-list"><p>Are you <b>The Synergist</b>, lighting up rooms?</p><p><b>The Innovator</b>, brimming with creativity?</p><p><b>The Mystic</b>, calm and insightful?</p><p>Or <b>The Adventurer</b>, fearless and spontaneous?</p></div><button className="quiz-button" onClick={()=>{setError('');setStep(0)}} disabled={!quiz}>Start</button></div>:result?<div className="quiz-result"><span className="quiz-kicker">YOUR PERSONALITY</span><h2>The {result.personality}</h2><p>{result.description}</p><div className="quiz-scores">{letters.map((letter,i)=><span key={letter}>{letter} · {result.scores?.[['Adventurer','Innovator','Mystic','Synergist'][i]]||0}</span>)}</div><button className="quiz-button" onClick={()=>{setResult(null);setAnswers(quiz.questions.map(()=>-1));setStep(-1)}}>Retake quiz</button></div>:quiz&&<div className="quiz-question-screen"><div className="quiz-progress"><span>QUESTION {step+1} OF {quiz.questions.length}</span><span>{Math.round((step+1)/quiz.questions.length*100)}%</span></div><div className="quiz-progress-track"><span style={{width:`${(step+1)/quiz.questions.length*100}%`}}/></div><h2>{quiz.questions[step].question}</h2><div className="quiz-options">{quiz.questions[step].options.map((o:string,j:number)=><button key={j} className={'quiz-option '+(answers[step]===j?'selected':'')} onClick={()=>setAnswers(answers.map((a,k)=>k===step?j:a))}><span className="quiz-radio"/>{o}<span className="quiz-letter">{letters[j]}</span></button>)}</div><div className="quiz-actions">{step>0&&<button className="quiz-back" onClick={()=>setStep(step-1)}>← Back</button>}<button className="quiz-button" disabled={answers[step]<0||busy} onClick={()=>step===quiz.questions.length-1?finish():setStep(step+1)}>{step===quiz.questions.length-1?(busy?'Calculating…':'See my result'):'Continue'}</button></div></div>}{error&&<p className="quiz-error" role="alert">{error}</p>}</div></section>
}

export function RegistrationForm({token,eventId,onDone}:{token:string;eventId:number;onDone:()=>void}) {
 const [fields,setFields]=useState<any[]>([]);const [answers,setAnswers]=useState<Record<string,string>>({});const [error,setError]=useState('');
 useEffect(()=>{fetch(`${API}/events/${eventId}/registration-fields`,{headers:{Authorization:`Bearer ${token}`}}).then(r=>r.json()).then(d=>setFields(d.fields||[])).catch(()=>setError('Unable to load registration form'))},[token,eventId]);
 return <form className="panel stack" onSubmit={async e=>{e.preventDefault();const r=await fetch(`${API}/events/${eventId}/register`,{method:'POST',headers:{'Content-Type':'application/json',Authorization:`Bearer ${token}`},body:JSON.stringify({answers})});const d=await r.json();if(r.ok)onDone();else setError(d.detail||'Registration failed')}}><h2>Event registration</h2><p>Complete your basic profile before registering.</p>{error&&<div className="alert">{error}</div>}{fields.map(f=><label key={f.label}>{f.label}{f.required?' *':''}<input maxLength={2000} required={f.required} value={answers[f.label]||''} onChange={e=>setAnswers({...answers,[f.label]:e.target.value})}/></label>)}<button className="button primary">Complete registration</button></form>
}

export function RegistrationFieldsEditor({token,eventId}:{token:string;eventId:number}) {
 const [fields,setFields]=useState<any[]>([]);const [status,setStatus]=useState('');const [answers,setAnswers]=useState<any[]>([]);
 useEffect(()=>{const h={Authorization:`Bearer ${token}`};fetch(`${API}/events/${eventId}/registration-fields`,{headers:h}).then(r=>r.json()).then(d=>setFields(d.fields||[]));fetch(`${API}/events/${eventId}/registration-answers`,{headers:h}).then(r=>r.json()).then(d=>setAnswers(Array.isArray(d)?d:[]))},[token,eventId]);
 return <div className="panel stack"><h2>Registration questions</h2><p>Add short-answer questions. Questions lock after the first registration.</p>{status&&<p>{status}</p>}{fields.map((f,i)=><div className="form-row" key={i}><input aria-label="Question" maxLength={200} value={f.label} onChange={e=>setFields(fields.map((x,j)=>j===i?{...x,label:e.target.value}:x))}/><label className="checkbox"><input type="checkbox" checked={f.required} onChange={e=>setFields(fields.map((x,j)=>j===i?{...x,required:e.target.checked}:x))}/>Required</label><button type="button" onClick={()=>setFields(fields.filter((_,j)=>j!==i))}>Remove</button></div>)}<button className="button outline" onClick={()=>setFields([...fields,{label:'',required:false}])}>Add question</button><button className="button primary" onClick={async()=>{const r=await fetch(`${API}/events/${eventId}/registration-fields`,{method:'PUT',headers:{'Content-Type':'application/json',Authorization:`Bearer ${token}`},body:JSON.stringify({fields})});const d=await r.json();setStatus(r.ok?'Questions saved.':d.detail||'Could not save')}}>Save questions</button>{answers.length>0&&<details><summary>View registration answers</summary>{answers.map(a=><div key={a.user_id}><b>{a.name}</b>{Object.entries(a.answers).map(([k,v])=><p key={k}>{k}: {String(v)}</p>)}</div>)}</details>}</div>
}

export function ProfileImport({token,profileUrl}:{token:string;profileUrl:string}) {
 const [url,setUrl]=useState(profileUrl||'');const [consent,setConsent]=useState(false);const [draft,setDraft]=useState<any>(null);const [values,setValues]=useState<Record<string,string>>({});const [selected,setSelected]=useState<string[]>([]);const [error,setError]=useState('');const [notice,setNotice]=useState('');const [busy,setBusy]=useState(false);
 useEffect(()=>{setUrl(profileUrl||'')},[profileUrl]);
 async function request(path:string, body:any){const r=await fetch(API+path,{method:'POST',headers:{'Content-Type':'application/json',Authorization:`Bearer ${token}`},body:JSON.stringify(body)});const d=await r.json();if(!r.ok)throw new Error(typeof d.detail==='string'?d.detail:'Unable to import profile');return d}
 async function preview(){setBusy(true);setError('');setNotice('');setDraft(null);try{const d=await request('/v2/profile/enrichment/preview',{url,consent});setDraft(d);setValues(d.suggestions);setSelected([])}catch(e:any){setError(e.message)}finally{setBusy(false)}}
 async function apply(){setBusy(true);setError('');try{await request('/v2/profile/enrichment/apply',{draft_token:draft.draft_token,fields:Object.fromEntries(selected.map(k=>[k,values[k]]))});setDraft(null);setConsent(false);setNotice('Selected suggestions saved.');window.dispatchEvent(new Event('beyond-profile-changed'));window.dispatchEvent(new Event('beyond-import-applied'))}catch(e:any){setError(e.message)}finally{setBusy(false)}}
 return <section className="panel stack"><h2>Import from a public profile</h2><p>Save other profile edits before importing. Exa retrieves the exact link and OpenAI proposes fields. Review each suggestion before saving. Some sites may not be accessible.</p><label>Public HTTPS link<input type="url" value={url} onChange={e=>{setUrl(e.target.value);setDraft(null);setConsent(false)}} placeholder="https://example.com/profile"/></label><label className="checkbox"><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)}/>I consent to Exa retrieving this link and OpenAI processing its contents for this import.</label><button type="button" className="button outline" disabled={!consent||!url||busy} onClick={preview}>{busy?'Working…':'Preview profile suggestions'}</button>{error&&<p className="alert">{error}</p>}{notice&&<p className="notice">{notice}</p>}{draft&&<><p>Source: <a href={draft.source_url} target="_blank" rel="noreferrer">{draft.source_url}</a>. Suggestions may be inaccurate; select and edit only what you want to save.</p>{Object.keys(values).map(k=><div className="stack" key={k}><label className="checkbox"><input type="checkbox" checked={selected.includes(k)} onChange={e=>setSelected(e.target.checked?[...selected,k]:selected.filter(x=>x!==k))}/>Apply {k.replaceAll('_',' ')}</label>{draft.current[k]&&<p className="small">Current: {draft.current[k]}</p>}<textarea aria-label={`Suggested ${k}`} value={values[k]} onChange={e=>setValues({...values,[k]:e.target.value})}/></div>)}<button type="button" className="button primary" disabled={!selected.length||busy} onClick={apply}>Apply selected suggestions</button><button type="button" className="text-button" onClick={()=>setDraft(null)}>Discard suggestions</button></>}</section>
}
