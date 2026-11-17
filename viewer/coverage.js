import {projectPoint} from './optics.js';
const COLORS=['#a3b0a1','#baac98','#91a7a8','#b6b994','#a7a0ae','#98aaa3'];
export function bookColor(book) { return COLORS[(book.id-1)%COLORS.length]; }
export function paintSpine(canvas, book, coverage) {
  const w=canvas.width,h=canvas.height,ctx=canvas.getContext('2d');
  ctx.fillStyle=bookColor(book);ctx.fillRect(0,0,w,h);
  ctx.fillStyle='rgba(243,245,237,.52)';ctx.fillRect(0,0,w,h);
  ctx.fillStyle='#369d81';
  const xs=book.x1-book.x0;
  for(let py=0;py<h;py+=3) {
    const y=book.height*(1-(py+1.5)/h),j=Math.floor(y/coverage.maxHeight*coverage.ny);
    if(j<0||j>=coverage.ny)continue;
    for(let px=0;px<w;px+=3) {
      const x=book.x0+(px+1.5)/w*xs;
      const i=Math.floor((x+380)/760*coverage.nx);
      if(coverage.mask[j*coverage.nx+i]) ctx.fillRect(px,py,3,3);
    }
  }
  ctx.fillStyle='rgba(35,55,43,.62)';ctx.font='500 28px sans-serif';ctx.textAlign='center';
  ctx.fillText(String(book.id).padStart(2,'0'),w/2,57);
  ctx.save();ctx.translate(w/2,h*.5);ctx.rotate(-Math.PI/2);ctx.font='22px sans-serif';ctx.fillText(`BOOK ${String(book.id).padStart(2,'0')}`,0,0);ctx.restore();
  ctx.fillStyle='rgba(255,255,255,.28)';ctx.fillRect(0,0,4,h);ctx.fillStyle='rgba(40,60,40,.12)';ctx.fillRect(w-4,0,4,h);
}
export function paintMap(canvas,c) {
  const ctx=canvas.getContext('2d');ctx.setTransform(2,0,0,2,0,0);ctx.clearRect(0,0,820,330);
  const left=56,top=20,W=760,H=250;
  ctx.fillStyle='#e8ece2';ctx.fillRect(left,top,W,H);
  for(const book of c.books){ctx.fillStyle='#d3d9cb';ctx.fillRect(left+book.x0+380+.6,top+H-book.height/c.maxHeight*H,book.x1-book.x0-1.2,book.height/c.maxHeight*H);}
  ctx.fillStyle='#2c9b7e';
  for(let j=0;j<c.ny;j++) for(let i=0;i<c.nx;i++) if(c.mask[j*c.nx+i]) {
    ctx.fillRect(left+i*W/c.nx,top+H-(j+1)*H/c.ny,W/c.nx+.1,H/c.ny+.1);
  }
  ctx.strokeStyle='#f3f5ed';ctx.lineWidth=1.7;
  for(const book of c.books){ctx.beginPath();ctx.moveTo(left+book.x1+380,top+H);ctx.lineTo(left+book.x1+380,top+H-book.height/c.maxHeight*H);ctx.stroke();}
  ctx.fillStyle='#7e8f7b';ctx.font='28px sans-serif';ctx.textAlign='right';
  for(const y of [0,c.maxHeight/2,c.maxHeight])ctx.fillText(String(Math.round(y)),left-8,top+H-y/c.maxHeight*H+10);
  ctx.textAlign='center';ctx.font='28px sans-serif';ctx.fillText('宽约 760 mm · 左右为整排书脊',left+W/2,318);
}

// Ideal sensor mapping through an equivalent anisotropic field of view.
// This deliberately does not claim to render a solved refractive lens.
export function paintProjection(canvas,c,s,vfov){
  const ctx=canvas.getContext('2d');ctx.setTransform(2,0,0,2,0,0);
  const W=800,H=450;ctx.clearRect(0,0,W,H);ctx.fillStyle='#e4e9de';ctx.fillRect(0,0,W,H);
  ctx.save();ctx.beginPath();ctx.rect(0,0,W,H);ctx.clip();
  const step=2;
  for(let j=0;j<c.ny;j+=step)for(let i=0;i<c.nx;i+=step){
    const k=Math.min(c.ny-1,j)*c.nx+Math.min(c.nx-1,i);
    if(!c.bookMask[k])continue;
    const x0=-s.width/2+i*s.width/c.nx,x1=-s.width/2+Math.min(c.nx,i+step)*s.width/c.nx;
    const y0=j*c.maxHeight/c.ny,y1=Math.min(c.ny,j+step)*c.maxHeight/c.ny;
    const points=[[x0,y0,s.spineZ],[x1,y0,s.spineZ],[x1,y1,s.spineZ],[x0,y1,s.spineZ]].map(p=>projectPoint(p,s,vfov));
    if(points.some(p=>!p))continue;
    ctx.fillStyle=c.mask[k]?'#359d7e':'#c5cebd';ctx.beginPath();
    points.forEach((p,index)=>{const x=(p.x+1)*W/2,y=(1-p.y)*H/2;index?ctx.lineTo(x,y):ctx.moveTo(x,y);});ctx.closePath();ctx.fill();
  }
  ctx.strokeStyle='#f5f7ef';ctx.lineWidth=1.1;
  for(const b of c.books){const a=projectPoint([b.x0,0,b.z],s,vfov),d=projectPoint([b.x0,b.height,b.z],s,vfov);if(!a||!d)continue;ctx.beginPath();ctx.moveTo((a.x+1)*W/2,(1-a.y)*H/2);ctx.lineTo((d.x+1)*W/2,(1-d.y)*H/2);ctx.stroke();}
  ctx.restore();
  ctx.strokeStyle='#b7c5b0';ctx.lineWidth=1;ctx.strokeRect(.5,.5,W-1,H-1);
  ctx.strokeStyle='#9aa996';ctx.setLineDash([6,8]);ctx.beginPath();ctx.moveTo(W/2,0);ctx.lineTo(W/2,H);ctx.moveTo(0,H/2);ctx.lineTo(W,H/2);ctx.stroke();ctx.setLineDash([]);
}
