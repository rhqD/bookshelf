// Millimetres: X across, Y above the selected shelf, Z inward from cabinet front.
// Camera + M1 layout proxy. Default physical coverage is supplied by sequential tracing.
import layout from '../data/optics/current-layout.json' with {type:'json'};
const pitch=layout.pitch_deg*Math.PI/180;
export const BASE=Object.freeze({
  width:760,height:328,depth:260,cameraY:layout.camera[1],cameraZ:layout.camera[2],
  aimY:layout.camera[1]+100*Math.sin(pitch),aimZ:layout.camera[2]-100*Math.cos(pitch),mirrorY:layout.mirror[1],mirrorZ:layout.mirror[2],
  m1Length:layout.mirror_size[0],m1Width:layout.mirror_size[1],mirrorTilt:layout.tilt_deg,
  hfov:115,vfov:82.88566833468566,bookDepth:200,spineZ:60,bookHeight:250,sensorAspect:16/9,
});
export const CYLINDERS=Object.freeze([]);
const dot=(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0);
const sub=(a,b)=>a.map((v,i)=>v-b[i]);
const length=a=>Math.hypot(...a);
const normalize=a=>{const n=length(a);return a.map(v=>v/n);};
const dist=(a,b)=>length(sub(a,b));

export function makeBooks(spineZ=BASE.spineZ,bookHeight=BASE.bookHeight){
  const widths=[31,24,38,20,28,33,22,36,25,30,18,35],offsets=[0,20,5,30,12,0,24,8];
  const books=[];let x=-BASE.width/2;
  while(x<BASE.width/2-.01){const i=books.length,w=Math.min(widths[i%widths.length],BASE.width/2-x);books.push({id:i+1,x0:x,x1:x+w,height:bookHeight-offsets[i%offsets.length],z:spineZ,depth:BASE.bookDepth});x+=w;}
  return books;
}
export function system(options={}){
  const p={...BASE,...options};
  const camera=[0,p.cameraY,p.cameraZ],mirror=[0,p.mirrorY,p.mirrorZ],aim=[0,p.aimY,p.aimZ];
  const angle=p.mirrorTilt*Math.PI/180,n=[0,Math.sin(angle),-Math.cos(angle)],tangent=[0,Math.cos(angle),Math.sin(angle)];
  const forward=normalize(sub(aim,camera)),up=[0,-forward[2],forward[1]];
  const d=dot(sub(camera,mirror),n),virtualCamera=camera.map((v,i)=>v-2*d*n[i]);
  return{...p,camera,mirror,aim,n,tangent,forward,up,virtualCamera,tanH:Math.tan(p.hfov*Math.PI/360),tanV:Math.tan(p.vfov*Math.PI/360)};
}
function intersectsBooks(a,b,s){
  let lo=0,hi=1;const min=[-s.width/2,0,s.spineZ],max=[s.width/2,s.bookHeight,s.spineZ+s.bookDepth];
  for(let i=0;i<3;i++){const d=b[i]-a[i];if(Math.abs(d)<1e-9){if(a[i]<min[i]||a[i]>max[i])return false;}else{let u=(min[i]-a[i])/d,v=(max[i]-a[i])/d;if(u>v)[u,v]=[v,u];lo=Math.max(lo,u);hi=Math.min(hi,v);if(lo>hi)return false;}}
  return hi>.0001&&lo<.9999;
}
export function trace(point,s){
  const direction=sub(point,s.virtualCamera),den=dot(direction,s.n);
  if(Math.abs(den)<1e-9)return{ok:false,reason:'direction'};
  const t=dot(sub(s.mirror,s.virtualCamera),s.n)/den;
  if(t<=0||t>=1)return{ok:false,reason:'direction'};
  const q1=s.virtualCamera.map((v,i)=>v+t*direction[i]);
  const delta=sub(q1,s.camera),depth=dot(delta,s.forward),vertical=dot(delta,s.up);
  const result={ok:false,q1,point,depth,sensorX:q1[0]/(depth*s.tanH),sensorY:vertical/(depth*s.tanV),reason:null};
  if(depth<=0||Math.abs(result.sensorX)>1+1e-9||Math.abs(result.sensorY)>1+1e-9){result.reason='field';return result;}
  if(Math.abs(q1[0])>s.m1Length/2+1e-6||Math.abs(dot(sub(q1,s.mirror),s.tangent))>s.m1Width/2+1e-6){result.reason='mirror';return result;}
  if([s.camera,q1,point].some(p=>Math.abs(p[0])>s.width/2+1e-6||p[1]<0||p[1]>s.height||p[2]<0||p[2]>s.depth)){result.reason='bay';return result;}
  for(const [a,b]of[[s.camera,q1],[q1,point]])if(intersectsBooks(a,b,s)){result.reason='books';return result;}
  result.ok=true;result.pathLength=dist(s.camera,q1)+dist(q1,point);
  result.spinePlaneAngleDeg=Math.atan2(Math.abs(point[2]-s.virtualCamera[2]),Math.hypot(point[0]-s.virtualCamera[0],point[1]-s.virtualCamera[1]))*180/Math.PI;
  return result;
}
export function projectPoint(point,s,vfov=s.vfov){
  const result=trace(point,s);if(!result.q1||result.depth<=0)return null;
  const tanV=Math.tan(vfov*Math.PI/360),vertical=dot(sub(result.q1,s.camera),s.up);
  return{x:result.sensorX,y:vertical/(result.depth*tanV),visible:result.ok};
}
export function ordinaryVerticalFov(s=system()){return 2*Math.atan(s.tanH/s.sensorAspect)*180/Math.PI;}
export function chiefPath(options={}){
  const s=system(options),den=dot(s.forward,s.n),t=dot(sub(s.mirror,s.camera),s.n)/den;
  const q=s.camera.map((v,i)=>v+t*s.forward[i]);
  const out=s.forward.map((v,i)=>v-2*dot(s.forward,s.n)*s.n[i]);
  const toSpine=(s.spineZ-q[2])/out[2];let end=q.map((v,i)=>v+toSpine*out[i]);
  let target='spine';
  if(end[1]<0){const tf=-q[1]/out[1];end=q.map((v,i)=>v+tf*out[i]);target='floor';}
  return{points:[s.camera,q,end],target};
}
export function sampleCoverage(options={}){
  const s=system(options),nx=152,ny=100,maxHeight=s.bookHeight,books=makeBooks(s.spineZ,maxHeight);
  const mask=new Uint8Array(nx*ny),bookMask=new Uint8Array(nx*ny),reasons={field:0,mirror:0,window:0,bay:0,books:0,direction:0};
  let total=0,visible=0,minAngle=Infinity,maxAngle=0;const fullRows=[];
  let minSensorY=Infinity,maxSensorY=-Infinity;
  for(let j=0;j<ny;j++){
    const y=(j+.5)*maxHeight/ny;let full=true;
    for(let i=0;i<nx;i++){
      const x=-s.width/2+(i+.5)*s.width/nx,b=books.find(b=>x>=b.x0&&x<=b.x1),k=j*nx+i;
      if(!b||y>b.height){full=false;continue;}bookMask[k]=1;total++;
      const r=trace([x,y,s.spineZ],s);
      if(r.ok){mask[k]=1;visible++;minAngle=Math.min(minAngle,r.spinePlaneAngleDeg);maxAngle=Math.max(maxAngle,r.spinePlaneAngleDeg);minSensorY=Math.min(minSensorY,r.sensorY);maxSensorY=Math.max(maxSensorY,r.sensorY);}else{full=false;reasons[r.reason]++;}
    }
    if(full)fullRows.push(j);
  }
  const bands=[];for(const row of fullRows){const last=bands[bands.length-1];if(last&&last.endRow===row-1){last.endRow=row;last.high=(row+1)*maxHeight/ny;}else bands.push({endRow:row,low:row*maxHeight/ny,high:(row+1)*maxHeight/ny});}
  return{nx,ny,maxHeight,books,mask,bookMask,total,visible,ratio:visible/total,bands,reasons,angles:visible?[minAngle,maxAngle]:null,verticalUsage:visible?(maxSensorY-minSensorY)/2:0};
}
export function installation(options={}){
  const s=system(options),halfY=s.m1Width/2*Math.abs(s.tangent[1])+.75*Math.abs(s.n[1]),halfZ=s.m1Width/2*Math.abs(s.tangent[2])+.75*Math.abs(s.n[2]);
  const cpath=chiefPath(options),ordinary=ordinaryVerticalFov(s);
  // Camera chassis remains a mechanical reference envelope.
  const cameraBottom=Math.min(s.cameraY-10*s.forward[1]-10*Math.abs(s.up[1])-7*Math.abs(s.forward[1]),s.cameraY-20*s.forward[1]-12*Math.abs(s.up[1])-Math.abs(s.forward[1]));

  return{pathLength:dist(cpath.points[0],cpath.points[1])+dist(cpath.points[1],cpath.points[2]),target:cpath.target,
    topClearance:s.height-(s.mirrorY+halfY),mirrorBookHeight:s.mirrorY-halfY-s.bookHeight,
    mirrorSpineClearance:s.spineZ-(s.mirrorZ+halfZ),cameraBookClearance:cameraBottom-s.bookHeight,
    cylinderCount:0,backClearance:s.depth-s.spineZ-s.bookDepth,
    mirrorSideClearance:(s.width-s.m1Length)/2,ordinaryVfov:ordinary,
    anamorphicRatio:Math.tan(ordinary*Math.PI/360)/s.tanV};
}
