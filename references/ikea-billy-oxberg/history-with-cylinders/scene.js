import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { BASE, system, trace, sampleCoverage, installation, chiefPath, CYLINDERS, lensCenter, ordinaryVerticalFov } from './optics.js';
import { paintMap, paintSpine, bookColor, paintProjection } from './coverage.js';

const $=id=>document.getElementById(id);
const stage=$('stage'), app=$('app'), loading=$('loading');
const FLOOR=1.062, FRONT=.120;
const world=p=>new THREE.Vector3(p[0]/1000,FLOOR+p[1]/1000,FRONT-p[2]/1000);
const state={spineZ:60,bookHeight:250,view:'bay',projection:'target'};

async function start(){
  const renderer=new THREE.WebGLRenderer({canvas:$('canvas'),antialias:true});
  renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.outputColorSpace=THREE.SRGBColorSpace;
  renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=.92;
  renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;renderer.localClippingEnabled=true;
  const scene=new THREE.Scene();scene.background=new THREE.Color(0xe7e9e3);
  const pmrem=new THREE.PMREMGenerator(renderer),room=new RoomEnvironment();
  const env=pmrem.fromScene(room,.04);scene.environment=env.texture;scene.environmentIntensity=.5;room.dispose();pmrem.dispose();
  scene.add(new THREE.HemisphereLight(0xffffff,0xa3b09b,.8));
  const key=new THREE.DirectionalLight(0xfff5e8,1.7);key.position.set(2,4,4);key.castShadow=true;key.shadow.mapSize.set(2048,2048);
  Object.assign(key.shadow.camera,{left:-2,right:2,top:3,bottom:-1,near:.1,far:12});key.shadow.normalBias=.0015;key.target.position.set(0,FLOOR,0);scene.add(key,key.target);
  const fill=new THREE.DirectionalLight(0xeaf1ff,.6);fill.position.set(-2,2,-2);scene.add(fill);
  const floor=new THREE.Mesh(new THREE.PlaneGeometry(200,200),new THREE.ShadowMaterial({opacity:.1}));floor.rotation.x=-Math.PI/2;floor.position.y=-.002;floor.receiveShadow=true;scene.add(floor);
  const camera=new THREE.OrthographicCamera(-1,1,1,-1,.01,40);
  const controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=true;controls.dampingFactor=.1;controls.minZoom=.4;controls.maxZoom=8;
  const data=Uint8Array.from(atob(MODEL_BASE64),c=>c.charCodeAt(0));
  const gltf=await new GLTFLoader().parseAsync(data.buffer,'');const model=gltf.scene;scene.add(model);
  const modelMaterials=[];
  model.traverse(o=>{if(!o.isMesh)return;o.castShadow=false;o.receiveShadow=true;
    const old=Array.isArray(o.material)?o.material:[o.material];
    const mats=old.map(m=>{const n=m.clone();modelMaterials.push({material:n,opacity:m.opacity,transparent:m.transparent});n.depthWrite=!n.transparent;return n;});o.material=Array.isArray(o.material)?mats:mats[0];
  });
  const sim=new THREE.Group();sim.position.set(0,FLOOR,FRONT);sim.scale.set(.001,.001,-.001);scene.add(sim);
  const basic=c=>new THREE.MeshBasicMaterial({color:c});
  const metal=new THREE.MeshStandardMaterial({color:0x667a78,roughness:.55,metalness:.45});
  const paleMetal=new THREE.MeshStandardMaterial({color:0x8c9e96,roughness:.55,metalness:.3});
  const cameraBlue=new THREE.MeshStandardMaterial({color:0x4278a8,roughness:.4,metalness:.25});
  const dark=new THREE.MeshStandardMaterial({color:0x2d4147,roughness:.5});
  const amber=basic(0xc78c35),purple=basic(0x9274af);
  const s0=system(),pose=new THREE.Matrix4().makeBasis(new THREE.Vector3(1,0,0),new THREE.Vector3(...s0.up),new THREE.Vector3(...s0.forward).negate());
  function box(size,pos,material,parent=sim){const m=new THREE.Mesh(new THREE.BoxGeometry(...size),material);m.position.set(...pos);m.castShadow=true;m.receiveShadow=true;parent.add(m);return m;}
  function tube(points,radius,color,parent=sim){const path=new THREE.CurvePath();for(let i=1;i<points.length;i++)path.add(new THREE.LineCurve3(new THREE.Vector3(...points[i-1]),new THREE.Vector3(...points[i])));const m=new THREE.Mesh(new THREE.TubeGeometry(path,Math.max(1,(points.length-1)*8),radius,6,false),color);parent.add(m);return m;}
  const roof=box([800,18,280],[0,BASE.height+9,130],new THREE.MeshStandardMaterial({color:0xd4ddd0,transparent:true,opacity:.13,depthWrite:false,side:THREE.DoubleSide}));roof.castShadow=false;
  const netBox=new THREE.Box3(new THREE.Vector3(-380,0,0),new THREE.Vector3(380,BASE.height,260));
  const bounds=new THREE.Box3Helper(netBox,0x9fae9c);bounds.material.transparent=true;bounds.material.opacity=.35;sim.add(bounds);
  // Camera body is a reference envelope around the assumed equivalent pupil.
  const cameraModule=new THREE.Group();cameraModule.position.set(...s0.camera);cameraModule.quaternion.setFromRotationMatrix(pose);sim.add(cameraModule);
  box([32,20,14],[0,0,10],cameraBlue,cameraModule);box([26,24,2],[0,0,20],dark,cameraModule);
  const lens=new THREE.Mesh(new THREE.CylinderGeometry(5,5,8,24),dark);lens.rotation.x=Math.PI/2;lens.position.set(0,0,1);cameraModule.add(lens);
  const pupil=new THREE.Mesh(new THREE.CircleGeometry(4,24),new THREE.MeshBasicMaterial({color:0x7fb2cb,side:THREE.DoubleSide}));pupil.rotation.y=Math.PI;pupil.position.set(0,0,-3.2);cameraModule.add(pupil);
  box([36,3,32],[0,BASE.height-1.5,244],paleMetal);box([4,38,10],[0,BASE.height-20,245],metal);
  tube([[12,BASE.cameraY,250],[18,BASE.height-4,251],[375,BASE.height-4,251],[375,25,251]],.9,dark);

  // Illustrative cylindrical surfaces, with no solved optical power or radii.
  function cylinderSurface(width,height,sag){
    const vertices=[],indices=[],N=24;
    for(let side=0;side<2;side++)for(let row=0;row<=N;row++)for(let x=0;x<2;x++){
      const u=row/N*2-1,z=side===0?1+sag*(1-u*u):-1;
      vertices.push((x-.5)*width,u*height/2,z);
    }
    const idx=(side,row,x)=>side*(N+1)*2+row*2+x;
    for(let row=0;row<N;row++){
      const a=idx(0,row,0),b=idx(0,row,1),c=idx(0,row+1,0),d=idx(0,row+1,1);indices.push(a,b,c,b,d,c);
      const e=idx(1,row,0),f=idx(1,row,1),g=idx(1,row+1,0),h=idx(1,row+1,1);indices.push(e,g,f,f,g,h);
      for(const x of[0,1]){const p=idx(0,row,x),q=idx(0,row+1,x),r=idx(1,row,x),t=idx(1,row+1,x);indices.push(p,r,q,q,r,t);}
    }
    for(const row of[0,N]){const a=idx(0,row,0),b=idx(0,row,1),c=idx(1,row,0),d=idx(1,row,1);indices.push(a,b,c,b,d,c);}
    const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));geometry.setIndex(indices);geometry.computeVertexNormals();return geometry;
  }
  const lensAssembly=new THREE.Group();sim.add(lensAssembly);const cylinderMaterials=[];
  for(let i=0;i<CYLINDERS.length;i++){
    const spec=CYLINDERS[i],center=lensCenter(spec,s0),group=new THREE.Group();group.position.set(...center);group.quaternion.setFromRotationMatrix(pose);lensAssembly.add(group);
    const mat=new THREE.MeshStandardMaterial({color:0xb7a4d8,metalness:.1,roughness:.14,transparent:true,opacity:.65,depthWrite:false,side:THREE.DoubleSide});cylinderMaterials.push(mat);
    const glass=new THREE.Mesh(cylinderSurface(spec.clearWidth,spec.clearHeight,i===0?-1.2:2.2),mat);group.add(glass);
    const edges=new THREE.LineSegments(new THREE.EdgesGeometry(glass.geometry,25),new THREE.LineBasicMaterial({color:0x826b9d}));group.add(edges);
    const frame=new THREE.MeshStandardMaterial({color:0x81748d,roughness:.5,metalness:.3});
    for(const sign of[-1,1]){
      box([spec.housingWidth,3,5],[0,sign*(spec.clearHeight/2+1.5),0],frame,group);
      box([3,spec.clearHeight,5],[sign*(spec.clearWidth/2+1.5),0,0],frame,group);
      const yTop=center[1]+spec.housingHeight/2,postX=sign*(spec.housingWidth/2+2);
      box([3,BASE.height-yTop,5],[postX,(BASE.height+yTop)/2,center[2]],paleMetal,lensAssembly);
      box([10,3,16],[postX,BASE.height-1.5,center[2]],metal,lensAssembly);
    }
  }
  function mirror(length,width,y,angle){
    const group=new THREE.Group();group.position.set(0,y,BASE.mirrorZ);sim.add(group);
    const material=new THREE.MeshStandardMaterial({color:0x91bdc7,metalness:.65,roughness:.2,side:THREE.DoubleSide,transparent:true,opacity:.62,depthWrite:false});
    const slab=box([length,width,1.5],[0,0,0],material,group);slab.rotation.x=angle;slab.castShadow=false;
    const edges=new THREE.LineSegments(new THREE.EdgesGeometry(slab.geometry),new THREE.LineBasicMaterial({color:0x3c8393}));edges.rotation.copy(slab.rotation);group.add(edges);
    return{group,slab,material};
  }
  const m1=mirror(BASE.m1Length,BASE.m1Width,BASE.mirrorY,BASE.mirrorTilt*Math.PI/180);
  for(const sign of[-1,1]){
    const x=sign*(BASE.m1Length/2+8),my=BASE.mirrorY,mz=BASE.mirrorZ;
    box([18,3,34],[x,BASE.height-2,mz],metal);box([4,BASE.height-my-3,10],[x,(BASE.height+my-3)/2,mz],metal);box([12,4,8],[sign*(BASE.m1Length/2+6),my,mz],metal);
    const screw=new THREE.Mesh(new THREE.CylinderGeometry(2.6,2.6,2,12),dark);screw.position.set(x,BASE.height-4,mz);sim.add(screw);
  }
  const bookGroup=new THREE.Group();sim.add(bookGroup);let bookViews=[];
  const beamGroup=new THREE.Group();sim.add(beamGroup);
  const floorOutline=new THREE.Box3Helper(new THREE.Box3(new THREE.Vector3(-.405,FLOOR-.01,-.145),new THREE.Vector3(.405,FLOOR+BASE.height/1000,.14)),0x6a9679);
  floorOutline.material.transparent=true;floorOutline.material.opacity=.6;scene.add(floorOutline);
  function disposeGroup(group){while(group.children.length){const o=group.children.pop();o.parent=null;o.geometry?.dispose();if(o.material && ![metal,paleMetal,dark,amber,purple].includes(o.material)){if(Array.isArray(o.material))o.material.forEach(m=>m.dispose());else o.material.dispose();}}}
  function buildBooks(cov){
    for(const view of bookViews){view.texture.dispose();view.mesh.geometry.dispose();view.materials.forEach(m=>m.dispose());}
    bookGroup.clear();bookViews=[];
    for(const b of cov.books){
      const canvas=document.createElement('canvas');canvas.width=96;canvas.height=512;paintSpine(canvas,b,cov);
      const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;texture.repeat.x=-1;texture.offset.x=1;texture.anisotropy=renderer.capabilities.getMaxAnisotropy();
      const pages=new THREE.MeshStandardMaterial({color:0xe5e5d7,roughness:.85});
      const cover=new THREE.MeshStandardMaterial({color:bookColor(b),roughness:.8});
      const spine=new THREE.MeshStandardMaterial({map:texture,roughness:.8});
      const mats=[cover,cover,pages,pages,pages,spine];
      const mesh=box([b.x1-b.x0-.7,b.height,b.depth],[(b.x0+b.x1)/2,b.height/2,b.z+b.depth/2],mats,bookGroup);
      bookViews.push({book:b,canvas,texture,mesh,materials:[pages,cover,spine]});
    }
  }
  function updateBooks(cov,rebuild){if(rebuild||!bookViews.length)buildBooks(cov);else for(const v of bookViews){paintSpine(v.canvas,v.book,cov);v.texture.needsUpdate=true;}}
  function drawBeams(){
    disposeGroup(beamGroup);const s=system(state),chief=chiefPath(state),points=chief.points;
    const front=lensCenter(CYLINDERS[1],s),rear=lensCenter(CYLINDERS[0],s);
    tube([front,points[1],points[2]],1.25,amber,beamGroup);
    function dashed(points,opacity=.8){const mat=new THREE.LineDashedMaterial({color:0x9679b1,dashSize:2.5,gapSize:1.5,transparent:true,opacity});const l=new THREE.Line(new THREE.BufferGeometry().setFromPoints(points.map(p=>new THREE.Vector3(...p))),mat);l.computeLineDistances();beamGroup.add(l);}
    dashed([s.camera,rear,front]);
    for(const [a0,b0]of[[front,points[1]],[points[1],points[2]]]){
      const a=new THREE.Vector3(...a0),b=new THREE.Vector3(...b0),dir=a.clone().sub(b).normalize(),origin=b.clone().lerp(a,.35);
      const arrow=new THREE.Mesh(new THREE.ConeGeometry(3,8,8),amber);arrow.position.copy(origin);arrow.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),dir);beamGroup.add(arrow);
    }
    for(const p of[points[1],points[2]]){const dot=new THREE.Mesh(new THREE.SphereGeometry(2.5,12,8),amber);dot.position.set(...p);beamGroup.add(dot);}
    const thin=new THREE.LineBasicMaterial({color:0xcda057,transparent:true,opacity:.48});
    for(const x of[-378,0,378])for(const y of[1,state.bookHeight/2,state.bookHeight-1]){
      const r=trace([x,y,state.spineZ],s);if(!r.ok)continue;
      const at=d=>s.camera.map((v,i)=>v+(r.q1[i]-v)*d/r.depth),entrance=at(CYLINDERS[1].distance);
      beamGroup.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([entrance,r.q1,r.point].map(p=>new THREE.Vector3(...p))),thin));
      dashed([s.camera,at(CYLINDERS[0].distance),entrance],.25);
    }
    beamGroup.visible=$('show-rays').checked;
  }
  let lastShape=null,currentCoverage=null;
  function drawSensor(){
    if(!currentCoverage)return;const s=system(state),vfov=state.projection==='target'?s.vfov:ordinaryVerticalFov(s);
    paintProjection($('sensor-projection'),currentCoverage,s,vfov);
    const usage=currentCoverage.verticalUsage*Math.tan(s.vfov*Math.PI/360)/Math.tan(vfov*Math.PI/360);
    $('sensor-usage').textContent=`约 ${(usage*100).toFixed(1)}%`;
    $('sensor-fov').textContent=`理想视场 ${s.hfov.toFixed(0)}° × ${vfov.toFixed(1)}°`;
    for(const b of document.querySelectorAll('[data-projection]'))b.setAttribute('aria-pressed',String(b.dataset.projection===state.projection));
  }
  function update(rebuild=false){
    state.spineZ=Number($('spine-depth').value);state.bookHeight=Number($('book-height').value);
    const shape=`${state.spineZ}:${state.bookHeight}`;if(lastShape!==shape){lastShape=shape;rebuild=true;}
    const cov=sampleCoverage(state);currentCoverage=cov;updateBooks(cov,rebuild);drawBeams();paintMap($('coverage'),cov);drawSensor();
    const fit=installation(state);
    const collision=fit.cameraBookClearance<0||fit.groupBookClearance<0||fit.mirrorBookHeight<0;
    $('installation-status').hidden=!collision;
    $('installation-status').textContent=collision?'当前部件占位与书本相交；覆盖图仅作理想光线示意，此尺寸不可直接安装。':'';
    $('spine-depth-value').textContent=`${state.spineZ} mm`;$('book-height-value').textContent=`${state.bookHeight} mm`;
    $('coverage-percent').textContent=`${(cov.ratio*100).toFixed(1)}%`;
    $('full-band').textContent=cov.bands.length?`全排共同书脊高度中，可见带约 ${cov.bands.map(b=>`${Math.round(b.low)}–${Math.round(b.high)}`).join('、')} mm`:'当前没有贯穿整排的完整可见带';
    $('angle-range').textContent=cov.angles?`${cov.angles[0].toFixed(1)}–${cov.angles[1].toFixed(1)}°`:'—';
    $('path-length').textContent=`${fit.pathLength.toFixed(1)} mm`;$('top-clearance').textContent=`${fit.topClearance.toFixed(1)} mm`;
    $('mirror-book-clearance').textContent=`${fit.mirrorBookHeight.toFixed(1)} mm`;$('lens-book-clearance').textContent=`${fit.groupBookClearance.toFixed(1)} mm`;
    $('chief-target').textContent=fit.target==='spine'?'中心视线到达书脊':'中心视线落在层板';
    const notes=[];
    if(fit.cameraBookClearance<0)notes.push(`相机占位与书本相交约 ${(-fit.cameraBookClearance).toFixed(1)} mm`);
    if(fit.groupBookClearance<0)notes.push(`镜组占位与书本相交约 ${(-fit.groupBookClearance).toFixed(1)} mm`);
    if(fit.backClearance<0)notes.push(`200 mm 深的书超出后板 ${(-fit.backClearance).toFixed(0)} mm`);
    if(!notes.length)notes.push(fit.backClearance===0?'书背与后板余量为 0 mm；镜框和公差仍需实测':'此为目标视场下的几何示例；安装尺寸需实测');
    $('fit-note').textContent=notes.join('；')+'。';
    $('coverage').setAttribute('aria-label',`目标等效镜组下，约 ${(cov.ratio*100).toFixed(1)}% 的示例书脊面积几何可达。不是 OCR 或实镜成像验证。`);
    app.dataset.coverage=(cov.ratio*100).toFixed(1);app.dataset.mode='anamorphic-target';app.dataset.bookHeight=String(state.bookHeight);app.dataset.fit=collision?'collision':'clear';
  }
  const captions={bay:['单层剖视','顶部、右侧与门体剖开示意；光路按实际净空检查'],side:['侧面光路','书脊 → M1 → L2 / L1 → 摄像头；紫色虚线为镜组内等效传递'],front:['书脊正面','绿色为目标视场下的几何可达区域，非文字识别率'],cabinet:['整柜安装位置','相机、镜组与 M1 均位于本层书顶通道'],optics:['镜组占位放大','L1 / L2 曲率仅示意；间隔 20 mm，焦距和真实入瞳未求解']};
  let extent=1;
  function setView(name){
    state.view=name;const target=world([0,155,105]);let offset;
    if(name==='optics'){controls.target.copy(world(lensCenter(CYLINDERS[1],s0)));offset=new THREE.Vector3(.15,.105,.20);extent=.17;}
    else if(name==='cabinet'){controls.target.set(0,1.04,0);offset=new THREE.Vector3(2.3,1.2,4);extent=2.65;}
    else{controls.target.copy(target);offset=name==='side'?new THREE.Vector3(1.5,.04,0):name==='front'?new THREE.Vector3(0,.01,1.8):new THREE.Vector3(1.0,.7,1.45);extent=name==='side'?.64:.76;}
    camera.position.copy(controls.target).add(offset);camera.zoom=1;camera.updateProjectionMatrix();controls.update();
    const cut=[new THREE.Plane(new THREE.Vector3(0,1,0),-(FLOOR-.023)),new THREE.Plane(new THREE.Vector3(0,-1,0),FLOOR+BASE.height/1000-.0005),new THREE.Plane(new THREE.Vector3(-1,0,0),.380),new THREE.Plane(new THREE.Vector3(0,0,-1),FRONT-.001)];
    for(const entry of modelMaterials){const m=entry.material;m.clippingPlanes=name==='cabinet'?[]:cut;m.opacity=name==='cabinet'?.2:entry.opacity;m.transparent=name==='cabinet'||entry.transparent;m.depthWrite=name!=='cabinet'&&!entry.transparent;m.needsUpdate=true;}
    roof.visible=name!=='cabinet'&&name!=='optics';bounds.visible=roof.visible;floorOutline.visible=name==='cabinet';floor.visible=name==='cabinet';model.visible=name!=='optics';bookGroup.visible=name!=='optics';m1.group.visible=name!=='optics';
    for(const b of document.querySelectorAll('[data-view]'))b.setAttribute('aria-pressed',String(b.dataset.view===name));
    $('view-caption').replaceChildren(document.createTextNode(captions[name][0]));const small=document.createElement('small');small.textContent=captions[name][1];$('view-caption').appendChild(small);
    resize();
  }
  function resize(){const w=stage.clientWidth,h=stage.clientHeight,aspect=w/h;const horizontal=state.view==='cabinet'?1.5:state.view==='side'?.52:state.view==='optics'?.23:1.02;const vertical=Math.max(extent,horizontal/aspect);camera.top=vertical/2;camera.bottom=-vertical/2;camera.left=-vertical*aspect/2;camera.right=vertical*aspect/2;camera.updateProjectionMatrix();renderer.setSize(w,h,false);}
  new ResizeObserver(resize).observe(stage);
  for(const button of document.querySelectorAll('[data-view]'))button.addEventListener('click',()=>setView(button.dataset.view));
  $('spine-depth').addEventListener('input',()=>update());$('book-height').addEventListener('input',()=>update());
  for(const b of document.querySelectorAll('[data-projection]'))b.addEventListener('click',()=>{state.projection=b.dataset.projection;drawSensor();});
  $('show-rays').addEventListener('change',()=>beamGroup.visible=$('show-rays').checked);
  const cameraDialog=$('camera-dialog');
  $('show-camera-render').addEventListener('click',()=>cameraDialog.showModal());
  $('close-camera-render').addEventListener('click',()=>cameraDialog.close());
  for(const button of document.querySelectorAll('[data-camera-flip]'))button.addEventListener('click',()=>{
    const corrected=button.dataset.cameraFlip==='corrected';
    $('camera-render-img').style.transform=corrected?'scaleX(-1)':'none';
    $('camera-render-img').alt=corrected?'首轮具体处方逐面追迹画面，已数字水平翻转，未拉正透视或增强文字。':'首轮具体处方逐面追迹的原始镜像方向画面。';
    $('camera-orientation-note').textContent=corrected?'仅作数字水平翻转，未拉正透视、裁切或增强文字。':'单次反射产生左右镜像；保留完整传感器画面。';
    for(const b of document.querySelectorAll('[data-camera-flip]'))b.setAttribute('aria-pressed',String(b===button));
  });
  $('transparent-mirrors').addEventListener('change',()=>{for(const material of[m1.material,...cylinderMaterials]){material.opacity=$('transparent-mirrors').checked?.62:1;material.transparent=$('transparent-mirrors').checked;material.depthWrite=!material.transparent;material.needsUpdate=true;}});
  const anchors=[
    {id:'label-camera',p:()=>s0.camera,offset:[0,-65]},
    {id:'label-lenses',p:()=>lensCenter(CYLINDERS[1],s0),offset:[85,-10]},
    {id:'label-m1',p:()=>[-170,BASE.mirrorY,BASE.mirrorZ],offset:[-35,-40]},
    {id:'label-band',p:()=>[-160,Math.min(125,state.bookHeight/2),state.spineZ],offset:[-50,35]},
  ];
  const leaderSvg=$('callout-lines'),ns='http://www.w3.org/2000/svg';
  const leaders=anchors.map(()=>{const line=document.createElementNS(ns,'line');line.setAttribute('stroke','#8b9b89');line.setAttribute('stroke-width','1');line.setAttribute('opacity','.55');leaderSvg.appendChild(line);return line;});
  const projected=new THREE.Vector3();
  function labels(){
    const w=stage.clientWidth,h=stage.clientHeight,placed=[];
    const side=[[55,-65],[-85,-78],[-90,-22],[90,35]],overview=[[-95,-80],[90,-70],[15,-25],[-60,40]],zoom=[[65,-45],[-40,65],[0,0],[0,0]];
    anchors.forEach((a,i)=>{
      const el=$(a.id),p=[...a.p()];if(state.view==='side')p[0]=0;projected.copy(world(p)).project(camera);
      const ax=(projected.x*.5+.5)*w,ay=(-projected.y*.5+.5)*h;
      const hide=!$('show-labels').checked||projected.z<-1||projected.z>1||(state.view==='optics'&&i>1)||ax<-20||ax>w+20||ay<40||ay>h-45;
      el.hidden=hide;leaders[i].style.display=hide?'none':'';if(hide)return;
      const offsets=state.view==='side'?side[i]:state.view==='cabinet'?overview[i]:state.view==='optics'?zoom[i]:a.offset;
      const bw=el.offsetWidth,bh=el.offsetHeight,clamp=(v,lo,hi)=>Math.max(lo,Math.min(hi,v));
      let x=clamp(ax+offsets[0],bw/2+10,w-bw/2-10),y=clamp(ay+offsets[1],bh/2+62,h-bh/2-48);
      for(const d of[0,-55,55,-110,110]){const candidate={x,y:clamp(y+d,bh/2+62,h-bh/2-48),w:bw,h:bh};if(!placed.some(b=>Math.abs(candidate.x-b.x)<(bw+b.w)/2+8&&Math.abs(candidate.y-b.y)<(bh+b.h)/2+8)){y=candidate.y;break;}}
      placed.push({x,y,w:bw,h:bh});el.style.left=`${x}px`;el.style.top=`${y}px`;
      const endX=clamp(ax,x-bw/2,x+bw/2),endY=clamp(ay,y-bh/2,y+bh/2);
      for(const[k,v]of Object.entries({x1:ax,y1:ay,x2:endX,y2:endY}))leaders[i].setAttribute(k,String(v));
    });
  }
  update(true);setView('bay');loading.hidden=true;app.dataset.state='ready';
  renderer.setAnimationLoop(()=>{controls.update();renderer.render(scene,camera);labels();});
}
start().catch(error=>{console.error(error);app.dataset.state='error';loading.hidden=false;loading.textContent=`模型加载失败：${error.message}`;loading.setAttribute('role','alert');});
