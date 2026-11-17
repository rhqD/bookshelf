import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { BASE, system, trace, sampleCoverage, installation, chiefPath } from './optics.js';
import { paintMap, paintSpine, bookColor } from './coverage.js';

const $=id=>document.getElementById(id);
const stage=$('stage'), app=$('app'), loading=$('loading');
const FLOOR=1.062, FRONT=.120;
const world=p=>new THREE.Vector3(p[0]/1000,FLOOR+p[1]/1000,FRONT-p[2]/1000);
const state={spineZ:60,bookHeight:250,view:'bay'};
const active=ACTIVE_OPTICS;

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
  const amber=basic(0xc78c35);
  const s0=system(),pose=new THREE.Matrix4().makeBasis(new THREE.Vector3(1,0,0),new THREE.Vector3(...s0.up),new THREE.Vector3(...s0.forward).negate());
  function box(size,pos,material,parent=sim){const m=new THREE.Mesh(new THREE.BoxGeometry(...size),material);m.position.set(...pos);m.castShadow=true;m.receiveShadow=true;parent.add(m);return m;}
  function tube(points,radius,color,parent=sim){const path=new THREE.CurvePath();for(let i=1;i<points.length;i++)path.add(new THREE.LineCurve3(new THREE.Vector3(...points[i-1]),new THREE.Vector3(...points[i])));const m=new THREE.Mesh(new THREE.TubeGeometry(path,Math.max(1,(points.length-1)*8),radius,6,false),color);parent.add(m);return m;}
  const roof=box([800,18,280],[0,BASE.height+9,130],new THREE.MeshStandardMaterial({color:0xd4ddd0,transparent:true,opacity:.13,depthWrite:false,side:THREE.DoubleSide}));roof.castShadow=false;
  const netBox=new THREE.Box3(new THREE.Vector3(-380,0,0),new THREE.Vector3(380,BASE.height,260));
  const bounds=new THREE.Box3Helper(netBox,0x9fae9c);bounds.material.transparent=true;bounds.material.opacity=.35;sim.add(bounds);
  // Camera front-vertex reference; internal objective is kept, external cylinders removed.
  const cameraModule=new THREE.Group();cameraModule.position.set(...s0.camera);cameraModule.quaternion.setFromRotationMatrix(pose);sim.add(cameraModule);
  box([32,20,14],[0,0,10],cameraBlue,cameraModule);box([26,24,2],[0,0,20],dark,cameraModule);
  const lens=new THREE.Mesh(new THREE.CylinderGeometry(5,5,8,24),dark);lens.rotation.x=Math.PI/2;lens.position.set(0,0,1);cameraModule.add(lens);
  const pupil=new THREE.Mesh(new THREE.CircleGeometry(4,24),new THREE.MeshBasicMaterial({color:0x7fb2cb,side:THREE.DoubleSide}));pupil.rotation.y=Math.PI;pupil.position.set(0,0,-3.2);cameraModule.add(pupil);
  const boardCentre=s0.camera.map((v,i)=>v-20*s0.forward[i]);
  const supportY=(BASE.height+boardCentre[1])/2;
  box([36,3,28],[0,BASE.height-1.5,boardCentre[2]],paleMetal);
  box([4,BASE.height-boardCentre[1],8],[0,supportY,boardCentre[2]+5],metal);
  tube([[12,boardCentre[1],boardCentre[2]],[18,BASE.height-4,boardCentre[2]],[375,BASE.height-4,boardCentre[2]],[375,25,251]],.9,dark);

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
  function disposeGroup(group){while(group.children.length){const o=group.children.pop();o.parent=null;o.geometry?.dispose();if(o.material && ![metal,paleMetal,dark,amber].includes(o.material)){if(Array.isArray(o.material))o.material.forEach(m=>m.dispose());else o.material.dispose();}}}
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
  function isDefault(){return state.spineZ===60&&state.bookHeight===250;}
  function drawBeams(){
    disposeGroup(beamGroup);
    const paths=isDefault()?active.rayPaths:[chiefPath(state).points];
    const chiefIndex=isDefault()?Math.min(4,paths.length-1):0;
    const thin=new THREE.LineBasicMaterial({color:0xcda057,transparent:true,opacity:.48});
    paths.forEach((points,index)=>{
      if(index===chiefIndex)tube(points,1.05,amber,beamGroup);
      else beamGroup.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(points.map(p=>new THREE.Vector3(...p))),thin));
      if(index!==chiefIndex)return;
      for(const p of points.slice(-2)){const dot=new THREE.Mesh(new THREE.SphereGeometry(2.5,12,8),amber);dot.position.set(...p);beamGroup.add(dot);}
      for(const [a0,b0]of[[points.at(-3),points.at(-2)],[points.at(-2),points.at(-1)]]){
        const a=new THREE.Vector3(...a0),b=new THREE.Vector3(...b0),dir=a.clone().sub(b).normalize();
        const arrow=new THREE.Mesh(new THREE.ConeGeometry(3,8,8),amber);arrow.position.copy(b).lerp(a,.35);arrow.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),dir);beamGroup.add(arrow);
      }
    });
    if(!isDefault()){
      const s=system(state);
      for(const x of[-378,0,378])for(const y of[1,state.bookHeight/2,state.bookHeight-1]){
        const r=trace([x,y,state.spineZ],s);if(!r.ok)continue;
        beamGroup.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([s.camera,r.q1,r.point].map(p=>new THREE.Vector3(...p))),thin));
      }
    }
    beamGroup.visible=$('show-rays').checked;
  }
  let lastShape=null,currentCoverage=null;
  function drawSensor(){
    $('sensor-usage').textContent=`约 ${(active.spineSignalVerticalSpan*100).toFixed(1)}%`;
    $('sensor-fov').textContent='普通鱼眼物镜 · 无附加柱面镜';
    const opt=active.positionOptimization;
    if(opt){
      $('density-before').textContent=opt.before.minPxPerMm.toFixed(3);
      $('density-after').textContent=opt.after.minPxPerMm.toFixed(3);
      $('density-gain').textContent=`+${opt.gainPercent.toFixed(1)}%`;
      $('density-detail').textContent=`最差点位于底部两端；8 mm 字在最受压方向约 ${(opt.before.minPxPerMm*8).toFixed(1)} → ${(opt.after.minPxPerMm*8).toFixed(1)} 个原始像素。`;
      $('optimization-summary').textContent=`最差采样密度 ${opt.before.minPxPerMm.toFixed(3)} → ${opt.after.minPxPerMm.toFixed(3)} px/mm（+${opt.gainPercent.toFixed(1)}%）；${opt.after.checkedSpinePoints.toLocaleString()} 个实际书脊采样点全部触达。`;
      const before=opt.before.finitePupil,after=opt.after.finitePupil;
      $('optimization-blur').textContent=`有限光阑复核：${after.rows.length} 个物点、每点 ${after.samplesPerObject} 条光线。几何光斑 D80 中位数 ${before.medianGeometricD80NativePx.toFixed(2)} → ${after.medianGeometricD80NativePx.toFixed(2)} 个原始像素；像素密度增加不等同于同比的清晰度提升。`;
    }
  }
  function update(rebuild=false){
    state.spineZ=Number($('spine-depth').value);state.bookHeight=Number($('book-height').value);
    const shape=`${state.spineZ}:${state.bookHeight}`;if(lastShape!==shape){lastShape=shape;rebuild=true;}
    const cov=sampleCoverage(state);if(isDefault()){cov.mask=Uint8Array.from(active.mask);cov.ratio=active.ratio;cov.bands=active.bands;cov.angles=active.angles;}currentCoverage=cov;updateBooks(cov,rebuild);drawBeams();paintMap($('coverage'),cov);drawSensor();
    const fit=installation(state);
    const collision=fit.cameraBookClearance<0||fit.mirrorBookHeight<0;
    $('installation-status').hidden=!collision;
    $('installation-status').textContent=collision?'当前部件占位与书本相交；覆盖图仅作理想光线示意，此尺寸不可直接安装。':'';
    $('spine-depth-value').textContent=`${state.spineZ} mm`;$('book-height-value').textContent=`${state.bookHeight} mm`;
    $('coverage-percent').textContent=`${(cov.ratio*100).toFixed(1)}%`;
    $('full-band').textContent=cov.bands.length?`全排共同书脊高度中，可见带约 ${cov.bands.map(b=>`${Math.round(b.low)}–${Math.round(b.high)}`).join('、')} mm`:'当前没有贯穿整排的完整可见带';
    $('angle-range').textContent=cov.angles?`${cov.angles[0].toFixed(1)}–${cov.angles[1].toFixed(1)}°`:'—';
    $('path-length').textContent=`${fit.pathLength.toFixed(1)} mm`;$('top-clearance').textContent=`${fit.topClearance.toFixed(1)} mm`;
    $('mirror-book-clearance').textContent=`${fit.mirrorBookHeight.toFixed(1)} mm`;$('camera-book-clearance').textContent=`${fit.cameraBookClearance.toFixed(1)} mm`;
    $('chief-target').textContent=fit.target==='spine'?'中心视线到达书脊':'中心视线落在层板';
    const notes=[];
    if(fit.cameraBookClearance<0)notes.push(`相机占位与书本相交约 ${(-fit.cameraBookClearance).toFixed(1)} mm`);
    if(fit.backClearance<0)notes.push(`200 mm 深的书超出后板 ${(-fit.backClearance).toFixed(0)} mm`);
    if(!notes.length)notes.push(fit.backClearance===0?'书背与后板余量为 0 mm；镜框和公差仍需实测':'尺寸已改变，当前为布局近似；需重新逐面追迹');
    $('fit-note').textContent=notes.join('；')+'。';
    $('coverage').setAttribute('aria-label',`${isDefault()?'无柱面镜默认布局逐面追迹':'改动布局的针孔几何近似'}：约 ${(cov.ratio*100).toFixed(1)}% 的示例书脊面积可达，非文字识别率。`);
    $('coverage-mode').textContent=isDefault()?'默认布局 · 逐面追迹采样':'改动布局 · 针孔几何近似';
    $('label-band').querySelector('b').textContent=isDefault()?'绿色 · 采样光线触达':'绿色 · 针孔布局近似';
    app.dataset.coverage=(cov.ratio*100).toFixed(1);app.dataset.mode='camera-m1-no-cylinders';app.dataset.bookHeight=String(state.bookHeight);app.dataset.fit=collision?'collision':'clear';
  }
  const captions={bay:['单层剖视','相机前移、顶部镜面降低；金色线来自新位置的实际镜头追迹'],side:['侧面光路','书脊 → 顶部 M1 → 摄像头；默认布局显示实际逐面追迹的代表光线'],front:['书脊正面','绿色为采样光线触达，不代表书名可读'],cabinet:['整柜安装位置','摄像头与 M1 位于本层书顶通道'],optics:['相机安装放大','保留相机自带物镜；前方无附加镜片']};
  let extent=1;
  function setView(name){
    state.view=name;const target=world([0,155,105]);let offset;
    if(name==='optics'){controls.target.copy(world(s0.camera));offset=new THREE.Vector3(.15,.105,.20);extent=.17;}
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
  $('show-rays').addEventListener('change',()=>beamGroup.visible=$('show-rays').checked);
  const cameraDialog=$('camera-dialog');
  const rawFootnote=$('camera-assumption').textContent;
  function setCameraMode(mode){
    const expanded=mode==='compare'||mode==='rectified';
    const optimizing=mode==='optimization';
    $('camera-raw-frame').hidden=expanded||optimizing;
    $('optimization-comparison').hidden=!optimizing;
    $('mirror-comparison').hidden=mode!=='compare';
    $('mirror-rectified-frame').hidden=mode!=='rectified';
    $('rectification-links').hidden=!expanded;
    $('camera-dialog-title').textContent=optimizing?'安装位置优化 · 原始采样密度':expanded?'镜内图像 · 边线矫正':'单镜优化后 · 摄像头画面';
    $('camera-render-img').style.transform=mode==='corrected'?'scaleX(-1)':'none';
    $('camera-render-img').alt=mode==='corrected'?'无附加柱面镜的摄像头画面，仅数字水平翻转镜像。':'无附加柱面镜的相机原始镜像方向画面。';
    $('camera-orientation-note').textContent=optimizing?'相同镜头、传感器、光阑与镜面尺寸；只调整位置、角度并重新对焦。':expanded?'按镜内图像的镜框曲线和书脊边线，估计畸变与透视展开。':mode==='corrected'?'仅作水平镜像翻转，未展开透视。':'单次反射产生左右镜像；保留完整传感器画面。';
    $('camera-assumption').textContent=optimizing?'像素密度取书脊平面到原始传感器映射的最小奇异值，按全部书脊采样中的最低值比较。热图共用色阶。数值为几何采样能力；有限光阑像差另行追迹，尚未包含完整衍射、色差、实拍噪声或 OCR 验证。数值搜索结果不构成全局最优证明。':expanded?'本结果只读取镜内裁剪 PNG：从镜框曲线拟合径向畸变，再由 27 条书脊边线估计消失点并展开透视。书顶、间隙和底部背景保留观测像素。输出 3040 × 1000；纵向比例为显示设置，单张裁剪图不能确定真实物理长宽比。有效图像逐像素重采样自输入 PNG，镜框外透明；原有模糊仍保留。':rawFootnote;
    for(const b of document.querySelectorAll('[data-camera-flip]'))b.setAttribute('aria-pressed',String(b.dataset.cameraFlip===mode));
  }
  $('show-camera-render').addEventListener('click',()=>{setCameraMode('raw');cameraDialog.showModal();});
  for(const b of document.querySelectorAll('[data-open-rectification]'))b.addEventListener('click',()=>{setCameraMode('compare');cameraDialog.showModal();});
  for(const b of document.querySelectorAll('[data-open-optimization]'))b.addEventListener('click',()=>{setCameraMode('optimization');cameraDialog.showModal();});
  $('close-camera-render').addEventListener('click',()=>cameraDialog.close());
  for(const b of document.querySelectorAll('[data-camera-flip]'))b.addEventListener('click',()=>setCameraMode(b.dataset.cameraFlip));
  $('transparent-mirrors').addEventListener('change',()=>{for(const material of[m1.material]){material.opacity=$('transparent-mirrors').checked?.62:1;material.transparent=$('transparent-mirrors').checked;material.depthWrite=!material.transparent;material.needsUpdate=true;}});
  const anchors=[
    {id:'label-camera',p:()=>s0.camera,offset:[0,-65]},
    {id:'label-m1',p:()=>[-170,BASE.mirrorY,BASE.mirrorZ],offset:[-35,-40]},
    {id:'label-band',p:()=>[-160,Math.min(125,state.bookHeight/2),state.spineZ],offset:[-50,35]},
  ];
  const leaderSvg=$('callout-lines'),ns='http://www.w3.org/2000/svg';
  const leaders=anchors.map(()=>{const line=document.createElementNS(ns,'line');line.setAttribute('stroke','#8b9b89');line.setAttribute('stroke-width','1');line.setAttribute('opacity','.55');leaderSvg.appendChild(line);return line;});
  const projected=new THREE.Vector3();
  function labels(){
    const w=stage.clientWidth,h=stage.clientHeight,placed=[];
    const side=[[55,-65],[-90,-22],[90,35]],overview=[[-95,-80],[15,-25],[-60,40]],zoom=[[65,-45],[0,0],[0,0]];
    anchors.forEach((a,i)=>{
      const el=$(a.id),p=[...a.p()];if(state.view==='side')p[0]=0;projected.copy(world(p)).project(camera);
      const ax=(projected.x*.5+.5)*w,ay=(-projected.y*.5+.5)*h;
      const hide=!$('show-labels').checked||projected.z<-1||projected.z>1||(state.view==='optics'&&i>0)||ax<-20||ax>w+20||ay<40||ay>h-45;
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
  $('label-camera').querySelector('span').textContent=`前顶点高 ${BASE.cameraY.toFixed(1)} / 深 ${BASE.cameraZ.toFixed(1)} mm`;
  $('label-m1').querySelector('span').textContent=`${BASE.m1Length} × ${BASE.m1Width} mm / ${BASE.mirrorTilt.toFixed(1)}°`;
  $('camera-position-text').textContent=`相机前顶点高 ${BASE.cameraY.toFixed(1)} mm、深 ${BASE.cameraZ.toFixed(1)} mm，光轴向前并上仰 ${(Math.atan2(s0.forward[1],-s0.forward[2])*180/Math.PI).toFixed(1)}°。六片鱼眼物镜与 4000 × 2250 传感器保持不变。`;
  $('mirror-position-text').textContent=`中心高 ${BASE.mirrorY.toFixed(1)} mm、深 ${BASE.mirrorZ.toFixed(1)} mm；镜面 ${BASE.m1Length} × ${BASE.m1Width} mm，与竖直方向夹角 ${BASE.mirrorTilt.toFixed(1)}°。两端支架固定于上层板。`;
  update(true);setView('bay');loading.hidden=true;app.dataset.state='ready';
  renderer.setAnimationLoop(()=>{controls.update();renderer.render(scene,camera);labels();});
}
start().catch(error=>{console.error(error);app.dataset.state='error';loading.hidden=false;loading.textContent=`模型加载失败：${error.message}`;loading.setAttribute('role','alert');});
