"""Create swappable, character-free layered SVG environment placeholders."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / 'public' / 'worlds'
BACKEND_CONFIGS = Path(__file__).resolve().parents[1] / '..' / 'backend' / 'worlds'
PALETTES = {
    'plaza': ('#173d55', '#285e72', '#c1d4c2', '#e4c177'),
    'cafe': ('#4b3028', '#85563c', '#d6ae73', '#e7c58f'),
    'garden': ('#183f38', '#30634a', '#b8d2a4', '#f3c4ca'),
    'arcade': ('#31294c', '#60436b', '#b483c7', '#55c9dc'),
    'lab': ('#493d32', '#8f7351', '#dcc89e', '#93a984'),
}
ROOM_LABELS = {'plaza':'Discovery Plaza','cafe':'Conversation Café','garden':'Connection Garden','arcade':'Activity Arcade','lab':'Idea Lab'}

def svg(room: str, layer: str, colors: tuple[str, ...]) -> str:
    deep, ground, light, accent = colors
    head = f'<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080"><defs><linearGradient id="g" x2="0" y2="1"><stop stop-color="{deep}"/><stop offset="1" stop-color="{ground}"/></linearGradient><pattern id="p" width="96" height="96" patternUnits="userSpaceOnUse"><path d="M0 48h96M48 0v96" stroke="{light}" stroke-opacity=".09" stroke-width="3"/></pattern></defs>'
    if layer == 'background':
        shape = f'<rect width="1920" height="1080" fill="url(#g)"/><path d="M0 820 Q240 710 480 820 T960 810 T1440 820 T1920 790 V1080 H0Z" fill="{light}" opacity=".12"/><circle cx="1600" cy="170" r="120" fill="{accent}" opacity=".12"/>'
    elif layer == 'ground':
        if room == 'plaza':
            shape = f'<ellipse cx="960" cy="548" rx="845" ry="460" fill="{ground}" stroke="{light}" stroke-opacity=".5" stroke-width="24"/><ellipse cx="960" cy="548" rx="580" ry="320" fill="none" stroke="{light}" stroke-opacity=".21" stroke-width="14"/><path d="M890 80h140v320H890M130 480h370v130H130M1420 480h370v130h-370M1310 750l170 160" fill="none" stroke="{accent}" stroke-width="90" opacity=".55"/>'
        elif room == 'garden':
            shape = f'<path d="M160 890 Q310 720 255 540 Q210 350 430 280 Q660 190 810 340 Q920 440 835 570 Q730 735 920 840 Q1090 930 1260 800 Q1450 655 1640 770 Q1790 845 1790 930" fill="none" stroke="{light}" stroke-opacity=".86" stroke-width="180" stroke-linecap="round"/><path d="M690 400l240-20 55 105-250 32zM890 710h180v220H890z" fill="{accent}" opacity=".6"/>'
        else:
            shape = f'<rect x="96" y="70" width="1728" height="940" rx="140" fill="{ground}" stroke="{light}" stroke-opacity=".38" stroke-width="24"/><rect x="130" y="104" width="1660" height="872" rx="120" fill="url(#p)"/><ellipse cx="960" cy="580" rx="700" ry="350" fill="{light}" opacity=".09"/>'
    elif layer == 'midground':
        if room == 'plaza':
            shape = f'<circle cx="960" cy="540" r="166" fill="{deep}" opacity=".72" stroke="{accent}" stroke-width="22"/><circle cx="960" cy="540" r="94" fill="{light}" opacity=".2"/><path d="M850 530q110-100 220 0q-110 100-220 0z" fill="{accent}" opacity=".8"/><rect x="240" y="355" width="140" height="82" rx="18" fill="{deep}" stroke="{accent}" stroke-width="12"/><rect x="1530" y="355" width="140" height="82" rx="18" fill="{deep}" stroke="{light}" stroke-width="12"/>'
        elif room == 'cafe':
            shape = f'<rect x="635" y="110" width="650" height="190" rx="60" fill="{deep}" stroke="{accent}" stroke-width="24"/><g fill="{light}" stroke="{accent}" stroke-width="18"><circle cx="600" cy="590" r="118"/><circle cx="960" cy="530" r="124"/><circle cx="1320" cy="590" r="118"/></g><g fill="{deep}"><rect x="150" y="360" width="290" height="140" rx="60"/><rect x="1480" y="360" width="290" height="140" rx="60"/></g>'
        elif room == 'garden':
            shape = f'<path d="M665 460 Q900 325 1160 400 L1270 540 Q1120 740 960 765 Q770 700 665 560Z" fill="{deep}" stroke="{accent}" stroke-width="24"/><path d="M710 520Q950 445 1210 520" fill="none" stroke="{light}" stroke-width="18" opacity=".6"/><g fill="{deep}" stroke="{light}" stroke-width="18"><circle cx="350" cy="250" r="84"/><circle cx="1540" cy="365" r="130"/><circle cx="420" cy="815" r="75"/></g>'
        elif room == 'arcade':
            shape = f'<g fill="{deep}" stroke="{accent}" stroke-width="18"><rect x="135" y="230" width="270" height="490" rx="40"/><rect x="1510" y="230" width="270" height="420" rx="40"/><circle cx="980" cy="590" r="160"/><rect x="1190" y="130" width="320" height="90" rx="22"/><rect x="1280" y="710" width="250" height="115" rx="24"/></g><circle cx="690" cy="370" r="170" fill="{accent}" opacity=".14"/>'
        else:
            shape = f'<g fill="{deep}" stroke="{accent}" stroke-width="18"><rect x="650" y="95" width="620" height="120" rx="18"/><rect x="135" y="235" width="300" height="105" rx="20"/><rect x="1480" y="210" width="285" height="340" rx="24"/><rect x="660" y="430" width="600" height="190" rx="42"/><circle cx="1360" cy="680" r="145"/><rect x="190" y="670" width="330" height="160" rx="55"/></g>'
    else:
        shape = f'<g fill="{light}" opacity=".28"><path d="M80 140q180-170 360 0v70H80zM1480 140q180-170 360 0v70h-360z"/><circle cx="160" cy="170" r="90"/><circle cx="1760" cy="860" r="130"/></g><path d="M0 0h1920v42H0z" fill="{accent}" opacity=".25"/>'
    return head + shape + '</svg>'

def main() -> None:
    documents=[json.loads(path.read_text(encoding='utf-8')) for path in sorted(BACKEND_CONFIGS.glob('*.json'))]
    if len(documents)!=5: raise SystemExit('Expected the five canonical backend world configs.')
    data={'revision':documents[0]['revision'],'coordinateSystem':documents[0]['coordinateSystem'],'rooms':[doc['room'] for doc in documents]}
    for room in data['rooms']:
        rid = room['id']; colors = PALETTES[rid]; dest = PUBLIC / rid; dest.mkdir(parents=True, exist_ok=True)
        layers = []
        for layer_id, z in (('background',0),('ground',10),('midground',20),('foreground',40)):
            name = f'{layer_id}.svg'; content = svg(rid, layer_id, colors); (dest/name).write_text(content,encoding='utf-8')
            digest = hashlib.sha256(content.encode()).hexdigest(); layers.append({'id':layer_id,'file':name,'width':1920,'height':1080,'sha256':digest,'placeholder':True,'z':z})
            next(x for x in room['layers'] if x['id']==layer_id)['src']=f'/worlds/{rid}/{name}'
        (dest/'manifest.json').write_text(json.dumps({'roomId':rid,'label':ROOM_LABELS[rid],'coordinateSpace':[1920,1080],'layers':layers,'source':'Engineering placeholder; replace file content without changing room or layer IDs.'},indent=2)+'\n',encoding='utf-8')
    cafe=next(r for r in data['rooms'] if r['id']=='cafe')
    for table,x,y,seatx in (('west',600,740,510),('center',960,680,870),('east',1320,740,1230)):
        if not any(a['id']==f'cafe_table_{table}_second' for a in cafe['interactions']):
            cafe['interactions'].append({'id':f'cafe_table_{table}_second','anchor':{'x':seatx,'y':y},'radius':90,'priority':50,'action':{'type':'seat','seatGroup':f'cafe_{table}'},'label':f'Join {table} table'})
    garden=next(r for r in data['rooms'] if r['id']=='garden')
    if not any(c['id']=='south-bench' for c in garden['colliders']): garden['colliders'].append({'id':'south-bench','shape':'aabb','x':490,'y':740,'width':180,'height':58})
    garden_actions=[
      {'id':'garden_bench_west_second','anchor':{'x':440,'y':680},'radius':90,'priority':50,'action':{'type':'seat','seatGroup':'garden_west'},'label':'Sit by the garden'},
      {'id':'garden_bench_east_second','anchor':{'x':1640,'y':750},'radius':90,'priority':50,'action':{'type':'seat','seatGroup':'garden_east'},'label':'Sit by the garden'},
      {'id':'garden_bench_south','anchor':{'x':580,'y':850},'radius':90,'priority':50,'action':{'type':'seat','seatGroup':'garden_south'},'label':'Sit by the garden'},
      {'id':'garden_bench_south_second','anchor':{'x':740,'y':850},'radius':90,'priority':50,'action':{'type':'seat','seatGroup':'garden_south'},'label':'Sit by the garden'},
    ]
    known={a['id'] for a in garden['interactions']}
    garden['interactions'].extend(a for a in garden_actions if a['id'] not in known)
    plaza=next(r for r in data['rooms'] if r['id']=='plaza')
    spawn_tuning={'from_garden':(1600,700),'from_arcade':(320,700)}
    for spawn in plaza['spawns']:
        if spawn['id'] in spawn_tuning: spawn['x'],spawn['y']=spawn_tuning[spawn['id']]
    for rid,xy,facing in (('cafe',(960,790),'up'),('garden',(960,800),'up'),('arcade',(470,540),'right'),('lab',(1530,760),'up')):
        room=next(r for r in data['rooms'] if r['id']==rid)
        for spawn in room['spawns']:
            if spawn['id'] in ('default','from_plaza'): spawn['x'],spawn['y'],spawn['facing']=*xy,facing
    for room in data['rooms']:
        out={'revision':data['revision'],'coordinateSystem':data['coordinateSystem'],'room':room}
        (BACKEND_CONFIGS/f"{room['id']}.json").write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

if __name__ == '__main__': main()
