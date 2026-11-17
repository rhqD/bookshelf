import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';

const data=REPORT_DATA, assets=REPORT_ASSETS;
const names={baseline:'无附加柱面镜',moderate:'温和放大 · 两片柱面镜',high:'高倍率试算 · 两片柱面镜'};
const $=id=>document.getElementById(id);
let mode='sensor',variant='moderate',scene3d;
function asset(name,key){return assets[name][key];}
function metrics(){
  const body=$('metric-body');
  const rows=[['采样触达面积',d=>`${(d.sampledRayReach*100).toFixed(2)}%`],['书脊信号纵向跨度',d=>`${(d.spineSignalVerticalSpan*100).toFixed(1)}%`],['通光点的采样密度中位数',d=>`${d.medianNativePxPerMmVisible.toFixed(2)} px/mm`],['几何光斑 D80 中位数',d=>`${d.geometricSpots.medianGeometricD80NativePx.toFixed(2)} px`],['几何光斑 D80 最大值',d=>`${d.geometricSpots.maxGeometricD80NativePx.toFixed(2)} px`],['可复核光斑的物点',d=>`${d.geometricSpots.acceptedFields} / ${d.geometricSpots.points}`]];
  body.innerHTML=rows.map(([label,fn])=>`<tr><th>${label}</th>${data.map(d=>`<td>${fn(d)}</td>`).join('')}</tr>`).join('');
}
function show(next){
  mode=next;$('pictures').hidden=mode==='layout';$('assembly').hidden=mode!=='layout';
  document.querySelectorAll('[data-mode]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.mode===mode)));
  if(mode==='layout'){$('picture-note').textContent='实际曲面与通光口径占位 · 金色为数值追迹光路 · 拖动旋转';if(!scene3d)scene3d=start3d();return;}
  const labels={sensor:'完整传感器画面 · 仅翻转镜像',crop:'镜内裁切 · 各图按完整范围缩放',rectified:'同一观测图的几何展开 · 保留书顶与背景',centre:'中部同一物理区域的展开细节'};
  const key={sensor:'sensor',crop:'crop',rectified:'rectified',centre:'centre'}[mode];
  $('picture-note').textContent=labels[mode];
  data.forEach(d=>{const im=$(`image-${d.name}`);const unsupported=d.name==='high'&&(mode==='rectified'||mode==='centre');im.hidden=unsupported;if(d.name==='high')$('unreliable-high').hidden=!unsupported;if(!unsupported){im.src=asset(d.name,key);im.alt=`${names[d.name]}：${labels[mode]}`;}});
}
function parameters(){
  const d=data.find(d=>d.name===variant),p=d.prescriptionData,l=p.layout;
  $('variant-note').textContent=`相机前顶点 (0, ${l.camera[1].toFixed(1)}, ${l.camera[2].toFixed(1)}) mm；俯仰 ${l.pitch_deg.toFixed(2)}°。顶部 M1：${l.mirror_size.join(' × ')} mm。`;
  const surfaces=p.surfaces.filter(s=>s.name.startsWith('L'));
  $('lens-table').innerHTML=[0,1].map(i=>{const a=surfaces[i*2],b=surfaces[i*2+1];return `<tr><th>L${i+1}</th><td>${a.z.toFixed(2)} → ${b.z.toFixed(2)} mm</td><td>${a.radius.toFixed(2)} / ${b.radius.toFixed(2)} mm</td><td>${a.width} × ${a.height} mm</td></tr>`;}).join('');
  $('aperture-note').textContent=variant==='moderate'?'L2 有效通光口径已缩至 100 × 28 mm；外框占位约 106 × 34 mm。相机、镜片曲率与间距保持本轮温和方案参数。':'高倍率方案保留原试算口径，用于效果对照。';
}
async function start3d(){
  const stage=$('model-stage'),renderer=new THREE.WebGLRenderer({canvas:$('model'),antialias:true});
  renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.setClearColor(0xe7e9e3);
  const scene=new THREE.Scene();scene.add(new THREE.HemisphereLight(0xffffff,0x9fae9b,2));
  const key=new THREE.DirectionalLight(0xfff6e8,2.2);key.position.set(2,4,3);scene.add(key);
  const camera=new THREE.OrthographicCamera(-.55,.55,.35,-.35,.01,10);
  const controls=new OrbitControls(camera,renderer.domElement);controls.target.set(0,1.21,.015);camera.position.set(.9,1.78,1.3);controls.enableDamping=true;controls.update();
  const bytes=Uint8Array.from(atob(MODEL_BASE64),c=>c.charCodeAt(0));const gltf=await new GLTFLoader().parseAsync(bytes.buffer,'');
  const planes=[new THREE.Plane(new THREE.Vector3(0,1,0),-1.039),new THREE.Plane(new THREE.Vector3(0,-1,0),1.390),new THREE.Plane(new THREE.Vector3(-1,0,0),.380),new THREE.Plane(new THREE.Vector3(0,0,-1),.119)];renderer.localClippingEnabled=true;
  gltf.scene.traverse(o=>{if(!o.isMesh)return;const mats=(Array.isArray(o.material)?o.material:[o.material]).map(m=>{const c=m.clone();c.clippingPlanes=planes;c.transparent=true;c.opacity=.20;c.depthWrite=false;return c;});o.material=Array.isArray(o.material)?mats:mats[0];});scene.add(gltf.scene);
  const root=new THREE.Group();root.position.set(0,1.062,.120);root.scale.set(.001,.001,-.001);scene.add(root);
  const dynamic=new THREE.Group();root.add(dynamic);
  const mat=(color,extra={})=>new THREE.MeshStandardMaterial({color,roughness:.55,...extra});
  const green=mat(0x91a99d),blue=mat(0x4278a8),metal=mat(0x6c7c76,{metalness:.35});
  const glass=mat(0x77adbf,{transparent:true,opacity:.30,side:THREE.DoubleSide,depthWrite:false});
  const bookSpines=new Map();
  function spineMaterial(book){
    if(bookSpines.has(book.id))return bookSpines.get(book.id);
    const width=book.x1-book.x0-.7,height=book.height,ppm=6;
    const canvas=document.createElement('canvas');canvas.width=Math.ceil(width*ppm);canvas.height=Math.ceil(height*ppm);
    const ctx=canvas.getContext('2d');ctx.scale(canvas.width/width,canvas.height/height);
    const gradient=ctx.createLinearGradient(0,0,width,0);gradient.addColorStop(0,'#7f9a8c');gradient.addColorStop(.15,'#91a99d');gradient.addColorStop(.85,'#91a99d');gradient.addColorStop(1,'#819b8e');
    ctx.fillStyle=gradient;ctx.fillRect(0,0,width,height);
    ctx.fillStyle='#29483b';ctx.textAlign='center';ctx.textBaseline='middle';
    ctx.font='500 4.5px "PingFang SC","Microsoft YaHei",sans-serif';ctx.fillText(String(book.id).padStart(2,'0'),width/2,17);
    const font=Math.min(13,width*.68),leading=font*1.22,chars=Array.from(book.title);
    ctx.font=`500 ${font}px "PingFang SC","Microsoft YaHei",sans-serif`;
    const top=height*.44-(chars.length-1)*leading/2;
    chars.forEach((ch,i)=>ctx.fillText(ch,width/2,top+i*leading));
    ctx.strokeStyle='#597c69';ctx.lineWidth=.35;ctx.beginPath();ctx.moveTo(width*.23,height-39);ctx.lineTo(width*.77,height-39);ctx.stroke();
    ctx.font='400 3.4px "PingFang SC","Microsoft YaHei",sans-serif';ctx.fillText('示例图书',width/2,height-27,width-3);
    const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;
    texture.repeat.x=-1;texture.offset.x=1;texture.anisotropy=renderer.capabilities.getMaxAnisotropy();
    const material=mat(0xffffff,{map:texture,roughness:.8});bookSpines.set(book.id,material);return material;
  }
  const world=p=>new THREE.Vector3(p.x/1000,1.062+p.y/1000,.120-p.z/1000);
  const boxes=[];
  function box(size,pos,material,parent=dynamic){const mesh=new THREE.Mesh(new THREE.BoxGeometry(...size),material);mesh.position.set(...pos);parent.add(mesh);return mesh;}
  function build(){
    dynamic.traverse(o=>{o.geometry?.dispose();});dynamic.clear();
    const d=data.find(d=>d.name===variant),p=d.prescriptionData,l=p.layout;
    const pitch=THREE.MathUtils.degToRad(l.pitch_deg),tilt=THREE.MathUtils.degToRad(l.tilt_deg),C=new THREE.Vector3(...l.camera),F=new THREE.Vector3(0,Math.sin(pitch),-Math.cos(pitch)),U=new THREE.Vector3(0,Math.cos(pitch),Math.sin(pitch));
    const pose=new THREE.Matrix4().makeBasis(new THREE.Vector3(1,0,0),U,F.clone().negate());
    for(const b of data[0].books){
      const book=box([b.x1-b.x0-.7,b.height,200],[(b.x0+b.x1)/2,b.height/2,160],[green,green,green,green,green,spineMaterial(b)]);
      book.name=`${String(b.id).padStart(2,'0')} · ${b.title}`;
    }
    $('model').dataset.bookCount=String(data[0].books.length);
    $('model').setAttribute('aria-label',`${data[0].books.length}本示例图书已在书脊标注书名；拖动旋转、滚轮缩放。`);
    box([760,3,260],[0,328,130],mat(0xb5c1b0,{transparent:true,opacity:.14,depthWrite:false}));
    const cameraBody=box([32,20,18],C.clone().addScaledVector(F,-10).toArray(),blue);cameraBody.quaternion.setFromRotationMatrix(pose);
    const board=C.clone().addScaledVector(F,-21);const pcb=box([26,24,2],board.toArray(),metal);pcb.quaternion.copy(cameraBody.quaternion);
    box([4,328-board.y,7],[0,(328+board.y)/2,board.z],metal);
    const m=box([l.mirror_size[0],l.mirror_size[1],1.5],l.mirror,glass);m.rotation.x=tilt;
    const edge=new THREE.LineSegments(new THREE.EdgesGeometry(m.geometry),new THREE.LineBasicMaterial({color:0x438b9a}));edge.position.copy(m.position);edge.rotation.copy(m.rotation);dynamic.add(edge);
    for(const sign of[-1,1])box([4,328-l.mirror[1],8],[sign*(l.mirror_size[0]/2+5),(328+l.mirror[1])/2,l.mirror[2]],metal);
    const surfaces=p.surfaces.filter(s=>s.name.startsWith('L'));
    function point(x,y,z){return C.clone().add(new THREE.Vector3(x,0,0)).addScaledVector(U,y).addScaledVector(F,z);}
    function sag(sf,y){return sf.radius?sf.radius-Math.sign(sf.radius)*Math.sqrt(sf.radius**2-y*y):0;}
    for(let i=0;i<2;i++){
      const rear=surfaces[2*i],front=surfaces[2*i+1],positions=[],indices=[],ny=40;
      for(const sf of[rear,front])for(const x of[-sf.width/2,sf.width/2])for(let j=0;j<=ny;j++){
        const y=-sf.height/2+j*sf.height/ny;positions.push(...point(x,y,sf.z+sag(sf,y)).toArray());
      }
      const row=ny+1;
      for(let k=0;k<2;k++)for(let j=0;j<ny;j++){const a=k*row*2+j,b=a+row;indices.push(a,b,a+1,b,b+1,a+1);}
      for(const side of[0,1])for(let j=0;j<ny;j++){const a=side*row+j,b=a+row*2;indices.push(a,b,a+1,b,b+1,a+1);}
      for(const j of[0,ny]){const a=j,b=row+j,c=row*2+j,e=row*3+j;indices.push(a,b,c,b,e,c);}
      const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));geometry.setIndex(indices);geometry.computeVertexNormals();dynamic.add(new THREE.Mesh(geometry,glass));
      const centre=(rear.z+front.z)/2;
      for(const sign of[-1,1]){
        const rimDepth=Math.max(5,front.z-rear.z+2);
        const rail=box([rear.width+6,3,rimDepth],point(0,sign*(rear.height/2+1.5),centre).toArray(),metal);rail.quaternion.setFromRotationMatrix(pose);
        const side=box([3,rear.height,rimDepth],point(sign*(rear.width/2+1.5),0,centre).toArray(),metal);side.quaternion.setFromRotationMatrix(pose);
      }
      const anchor=point(0,rear.height/2+4,centre);box([3,328-anchor.y,5],[anchor.x,(328+anchor.y)/2,anchor.z],metal);
    }
    for(const path of d.rayPaths){const geometry=new THREE.BufferGeometry().setFromPoints(path.map(v=>new THREE.Vector3(...v)));dynamic.add(new THREE.Line(geometry,new THREE.LineBasicMaterial({color:0xc18b39,transparent:true,opacity:.7})));}
    const targets=[['C · 相机',C],['M1 · 顶部平面镜',new THREE.Vector3(...l.mirror)],['L1 · 近端负柱面镜',point(0,0,(surfaces[0].z+surfaces[1].z)/2)],[`L2 · ${surfaces[2].width} × ${surfaces[2].height} mm 通光口径`,point(0,0,(surfaces[2].z+surfaces[3].z)/2)]];
    $('model-labels').replaceChildren();
    targets.forEach(([text,p],i)=>{const el=document.createElement('span');el.textContent=text;el.className='model-label';$('model-labels').appendChild(el);boxes[i]={el,p:world(p),index:i};});
    parameters();paintLabels();
  }
  function paintLabels(){camera.updateMatrixWorld();for(const b of boxes){if(!b)continue;const v=b.p.clone().project(camera);const dx=[-10,-120,110,100][b.index],dy=[-60,-40,0,-100][b.index];b.el.style.left=`${Math.max(90,Math.min(stage.clientWidth-100,(v.x*.5+.5)*stage.clientWidth+dx))}px`;b.el.style.top=`${Math.max(45,Math.min(stage.clientHeight-30,(-v.y*.5+.5)*stage.clientHeight+dy))}px`;}}
  function size(){const w=stage.clientWidth,h=stage.clientHeight;if(!w||!h)return;const ratio=w/h,extent=Math.max(.64,.86/ratio);camera.top=extent/2;camera.bottom=-extent/2;camera.left=-extent*ratio/2;camera.right=extent*ratio/2;camera.updateProjectionMatrix();renderer.setSize(w,h,false);paintLabels();}
  new ResizeObserver(size).observe(stage);size();build();
  $('trial-select').addEventListener('change',()=>{variant=$('trial-select').value;build();});
  document.querySelectorAll('[data-view]').forEach(button=>button.addEventListener('click',()=>{camera.position.set(...(button.dataset.view==='side'?[1.6,1.23,.015]:button.dataset.view==='front'?[0,1.21,1.7]:[.9,1.78,1.3]));controls.update();}));
  controls.addEventListener('change',paintLabels);
  renderer.setAnimationLoop(()=>{controls.update();renderer.render(scene,camera);paintLabels();});
}

metrics();parameters();show(location.hash==='#layout'?'layout':'sensor');
document.querySelectorAll('[data-mode]').forEach(b=>b.addEventListener('click',()=>show(b.dataset.mode)));
document.querySelectorAll('[data-open-image]').forEach(a=>a.href=assets[a.dataset.openImage].nativeUrl);
document.documentElement.dataset.ready='true';
