import type { Point } from './types';
export function isBlocked(room:any,x:number,y:number,radius=28){
 const b=room.bounds;if(x<b.x+radius||x>b.x+b.width-radius||y<b.y+radius||y>b.y+b.height-radius)return true;
 const polygons=room.walkablePolygons||[],bridge=polygons.filter((p:any)=>p.id.includes('bridge')).some((p:any)=>pointInPolygon(x,y,p.points));
 if(polygons.length&&!bridge&&!polygons.filter((p:any)=>!p.id.includes('bridge')).some((p:any)=>pointInPolygon(x,y,p.points)))return true;
 return (room.colliders||[]).some((s:any)=>{
  if(bridge&&s.id==='central-pond')return false;
  if(s.shape==='circle')return Math.hypot(x-s.x,y-s.y)<s.radius+radius;
  if(s.shape==='aabb'){const px=Math.max(s.x,Math.min(x,s.x+s.width)),py=Math.max(s.y,Math.min(y,s.y+s.height));return Math.hypot(x-px,y-py)<radius}
  if(s.shape==='polygon'){const pts=s.points;return pointInPolygon(x,y,pts)||pts.some((a:number[],i:number)=>segmentDistance(x,y,a,pts[(i+1)%pts.length])<radius)}
  return false;
 });
}
function pointInPolygon(x:number,y:number,pts:number[][]){let inside=false;for(let i=0,j=pts.length-1;i<pts.length;j=i++){const [xi,yi]=pts[i],[xj,yj]=pts[j];if((yi>y)!==(yj>y)&&x<(xj-xi)*(y-yi)/((yj-yi)||1e-12)+xi)inside=!inside}return inside}
function segmentDistance(x:number,y:number,a:number[],b:number[]){const dx=b[0]-a[0],dy=b[1]-a[1],den=dx*dx+dy*dy,t=den?Math.max(0,Math.min(1,((x-a[0])*dx+(y-a[1])*dy)/den)):0;return Math.hypot(x-a[0]-dx*t,y-a[1]-dy*t)}
export function sweepMove(room:any,from:Point,to:Point):Point{const dx=to.x-from.x,dy=to.y-from.y,steps=Math.max(1,Math.ceil(Math.hypot(dx,dy)/6));let x=from.x,y=from.y;for(let i=1;i<=steps;i++){const nx=from.x+dx*i/steps,ny=from.y+dy*i/steps;if(isBlocked(room,nx,ny)){if(!isBlocked(room,nx,y))x=nx;else if(!isBlocked(room,x,ny))y=ny;break}x=nx;y=ny}return{x,y}}
