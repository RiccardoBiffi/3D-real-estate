/* Three.js MIT. Source-traced geometry is supplied as MODEL_DATA by build-model.mjs. */
import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js';

const data=window.MODEL_DATA, canvas=document.querySelector('canvas');
const renderer=new THREE.WebGLRenderer({canvas,antialias:true,preserveDrawingBuffer:true});
renderer.setPixelRatio(Math.min(devicePixelRatio,1.7));renderer.shadowMap.enabled=true;
renderer.shadowMap.type=THREE.PCFSoftShadowMap;renderer.shadowMap.autoUpdate=false;renderer.setClearColor('#ebe9e2');
renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=data.rendering?.exposure??1.0;
const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(38,1,.1,2000);
let activeCamera=camera,mode=0,frames=0,paused=false,lost=false,planMode=false;
const controls=new OrbitControls(camera,canvas);controls.enableDamping=true;controls.dampingFactor=.14;
controls.minPolarAngle=.04;controls.maxPolarAngle=Math.PI/2-.025;
controls.mouseButtons={LEFT:THREE.MOUSE.ROTATE,MIDDLE:THREE.MOUSE.DOLLY,RIGHT:THREE.MOUSE.PAN};
controls.touches={ONE:THREE.TOUCH.ROTATE,TWO:THREE.TOUCH.DOLLY_PAN};
const materialCache=new Map();
const finishes = new Map();
function floorMaterial(color,finish){
 if(!finish)return mat(color);
 const key=color+finish;
 if(finishes.has(key))return finishes.get(key);
 const c=document.createElement('canvas');c.width=c.height=256;
 const ctx=c.getContext('2d');ctx.fillStyle=color;ctx.fillRect(0,0,256,256);
 let seed=411;const rand=()=>((seed=(seed*16807)%2147483647)/2147483647);
 if(finish==='wood'){
  for(let y=0;y<256;y+=24){
   ctx.fillStyle='rgba(88,59,41,'+(rand()*.12)+')';ctx.fillRect(0,y,256,24);ctx.fillStyle='rgba(65,46,35,.18)';ctx.fillRect(0,y,256,1);ctx.fillRect(Math.floor(rand()*245),y,1,24);
   for(let i=0;i<12;i++){ctx.fillStyle='rgba(76,51,36,.07)';ctx.fillRect(rand()*256,y+rand()*22,12+rand()*74,.6);}
  }
 }else{
  ctx.fillStyle='rgba(73,66,59,.23)';for(let i=0;i<256;i+=64){ctx.fillRect(i,0,1,256);ctx.fillRect(0,i,256,1);}
 }
 const map=new THREE.CanvasTexture(c);map.wrapS=map.wrapT=THREE.RepeatWrapping;map.repeat.set(.42,.42);map.colorSpace=THREE.SRGBColorSpace;
 const material=new THREE.MeshStandardMaterial({map,roughness:.85});finishes.set(key,material);return material;
}
function texturedMaterial(color='#e8dfca',roughness=.8){let key=color+roughness;if(!materialCache.has(key)){if(!data.rendering?.textured){const material=new THREE.MeshStandardMaterial({color,roughness});materialCache.set(key,material);return material;}const c=document.createElement('canvas');c.width=c.height=128;const ctx=c.getContext('2d');ctx.fillStyle=color;ctx.fillRect(0,0,128,128);let seed=17;for(let i=0;i<6000;i++){seed=(seed*16807)%2147483647;const x=seed%128;seed=(seed*16807)%2147483647;const y=seed%128;ctx.fillStyle=i%2?'rgba(255,255,255,.035)':'rgba(0,0,0,.04)';ctx.fillRect(x,y,2,2);}if(color==='#bdb7a8'){ctx.fillStyle='#817d70';ctx.fillRect(0,0,128,128);for(let row=0;row<8;row++)for(let col=0;col<5;col++){const x=col*29-(row%2)*12,y=row*17;ctx.fillStyle=['#b8b4a7','#d0c9bb','#c1bdae','#c9c6b7'][(col+row)%4];ctx.beginPath();ctx.moveTo(x+2,y+2);ctx.lineTo(x+24,y);ctx.lineTo(x+28,y+12);ctx.lineTo(x+4,y+16);ctx.closePath();ctx.fill();}}const tex=new THREE.CanvasTexture(c);tex.colorSpace=THREE.SRGBColorSpace;tex.wrapS=tex.wrapT=THREE.RepeatWrapping;tex.repeat.set(3,3);materialCache.set(key,new THREE.MeshStandardMaterial({color:'#ffffff',map:tex,roughness}));}return materialCache.get(key);}
function mat(color='#e8dfca',roughness=.8){if(data.rendering?.textured)return texturedMaterial(color,roughness);let key=color+roughness;if(!materialCache.has(key))materialCache.set(key,new THREE.MeshStandardMaterial({color,roughness}));return materialCache.get(key);}
function mesh(geo,material,group){const obj=new THREE.Mesh(geo,material);obj.castShadow=true;obj.receiveShadow=true;group.add(obj);return obj;}
function box(group,center,size,color,roughness){const obj=mesh(new THREE.BoxGeometry(...size),mat(color,roughness),group);obj.position.set(...center);return obj;}
function beam(group,a,b,color,radius=.025){const A=new THREE.Vector3(...a),B=new THREE.Vector3(...b),delta=B.clone().sub(A);const obj=mesh(new THREE.CylinderGeometry(radius,radius,delta.length(),8),mat(color),group);obj.position.copy(A.add(B).multiplyScalar(.5));obj.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),delta.normalize());return obj;}
function polygon(group,points,y,thickness,color,holes=[],finish=null){const shape=new THREE.Shape(points.map(p=>new THREE.Vector2(p[0],-p[1])));for(const p of holes)shape.holes.push(new THREE.Path(p.map(q=>new THREE.Vector2(q[0],-q[1]))));const obj=mesh(new THREE.ExtrudeGeometry(shape,{depth:thickness,bevelEnabled:false}),floorMaterial(color,finish),group);obj.rotation.x=-Math.PI/2;obj.position.y=y-thickness;return obj;}
function segment(group,a,b,y,h,thickness,color,category='wall'){const length=Math.hypot(b[0]-a[0],b[1]-a[1]);if(length<.0001||h<=0)return;const obj=box(group,[(a[0]+b[0])/2,y+h/2,(a[1]+b[1])/2],[length,h,thickness],color);obj.rotation.y=-Math.atan2(b[1]-a[1],b[0]-a[0]);obj.userData.category=category;return obj;}
function lining(panel){
 if(!panel)return;
 const dimensions=panel.geometry.parameters,face=mesh(new THREE.PlaneGeometry(dimensions.width,dimensions.height),mat('#eae5dc'),panel.parent);
 face.position.copy(panel.position);face.rotation.copy(panel.rotation);face.translateZ(dimensions.depth/2+.0015);face.castShadow=false;
}
function wall(group,w,y,height){const len=Math.hypot(w.b[0]-w.a[0],w.b[1]-w.a[1]),dx=(w.b[0]-w.a[0])/len,dz=(w.b[1]-w.a[1])/len,t=w.thickness||.18,openings=(w.openings||[]).slice().sort((a,b)=>a.start-b.start);let end=0;
 const panel=(a,b,base,h)=>{const piece=segment(group,a,b,base,h,t,w.color||data.colors?.walls||'#e7dfc8');if(w.insideFace)lining(piece);};
 const pt=s=>[w.a[0]+s*dx,w.a[1]+s*dz];
 for(const op of openings){const start=Math.max(end,op.start),finish=Math.min(len,op.end);if(finish<=start)continue;panel(pt(end),pt(start),y,height);const sill=Math.min(height,op.sill??0),top=Math.min(height,sill+(op.height??2.05));panel(pt(start),pt(finish),y,Math.min(sill,height));panel(pt(start),pt(finish),y+top,height-top);
  if(op.kind==='window'&&height>1.4){const glass=mesh(new THREE.BoxGeometry(finish-start,Math.max(.1,top-sill),.018),new THREE.MeshStandardMaterial({color:'#9ac2c6',transparent:true,opacity:.34,roughness:.15}),group);glass.position.set(...[...pt((start+finish)/2).slice(0,1),y+(sill+top)/2,pt((start+finish)/2)[1]]);glass.rotation.y=-Math.atan2(dz,dx);glass.castShadow=false;
   const frameColor=data.colors?.frames||'#7c6550';segment(group,pt(start),pt(finish),y+sill,.06,.075,frameColor);segment(group,pt(start),pt(finish),y+top-.06,.06,.075,frameColor);for(const s of [start,finish])box(group,[pt(s)[0],y+(sill+top)/2,pt(s)[1]],[.05,top-sill,.05],frameColor);
  }end=finish;
 }panel(pt(end),pt(len),y,height);
}
function furnishing(group,f,y){const g=new THREE.Group();group.add(g);g.position.set(f.x,y,f.z);g.rotation.y=f.rotation||0;const w=f.width||1.6,d=f.depth||.8,c=f.color||'#a49379';
 if(f.kind==='bed'){box(g,[0,.28,0],[w,.18,d||2],data.colors?.wood||'#846244');box(g,[0,.45,0],[w-.05,.22,d||2],'#e3dacc');box(g,[0,.58,.25],[w,.06,(d||2)*.65],c);box(g,[0,.65,-(d||2)/2],[w,.95,.10],data.colors?.wood||'#846244');for(const s of [-1,1])box(g,[s*w*.24,.60,-d*.34],[w*.38,.13,.38],'#f1ebe0');}
 else if(f.kind==='sofa'){box(g,[0,.34,0],[w,.45,d],c);box(g,[0,.68,-d*.39],[w,.70,.18],c);for(const s of [-1,1])box(g,[s*w*.46,.54,0],[.18,.48,d],c);for(const s of [-1,1])box(g,[s*w*.23,.60,.07],[w*.43,.13,d*.65],c);}
 else if(f.kind==='table'){if(f.round){const top=mesh(new THREE.CylinderGeometry(w/2,w/2,.08,36),mat(c),g);top.position.y=.76;top.scale.z=d/w;}else box(g,[0,.76,0],[w,.09,d],c);for(const a of [-1,1])for(const b of [-1,1])box(g,[a*(w/2-.1),.36,b*(d/2-.1)],[.07,.72,.07],data.colors?.wood||'#846244');}
 else if(f.kind==='chair'){box(g,[0,.45,0],[w,.06,d],c);box(g,[0,.73,-d*.45],[w,.62,.055],c);for(const a of [-1,1])for(const b of [-1,1])box(g,[a*w*.4,.21,b*d*.4],[.045,.42,.045],data.colors?.wood||'#846244');}
 else if(f.kind==='toilet'){box(g,[0,.24,0],[.40,.46,.54],'#eeeae1');box(g,[0,.54,-.20],[.40,.62,.13],'#eeeae1');}
 else if(f.kind==='basin'){box(g,[0,.42,0],[w,.80,d],c);box(g,[0,.85,0],[w+.03,.12,d+.03],'#f1eee4');}
 else if(f.kind==='bath'){box(g,[0,.29,0],[w,.56,d],'#e8e5db');box(g,[0,.58,0],[w-.08,.025,d-.08],'#b1bcb7');}
 else if(f.kind==='kitchen'){
  box(g,[0,.44,0],[w,.87,d],c);box(g,[0,.90,0],[w+.025,.075,d+.025],f.counter||'#c7c4b8');
  const count=Math.max(1,Math.round(w/.60)),unit=w/count;
  for(let i=0;i<count;i++){const x=-w/2+(i+.5)*unit;box(g,[x,.47,d/2+.01],[unit-.025,.72,.025],c);box(g,[x,.72,d/2+.04],[Math.min(.22,unit*.5),.025,.035],'#766e61');}
  if(w>1.5){box(g,[-w*.27,.948,.02],[.43,.018,d*.63],'#878e8e');box(g,[w*.23,.948,0],[.48,.018,d*.73],'#444642');}
 }
 else if(['cabinet','wardrobe','bookcase'].includes(f.kind)){
  const h=f.height||(f.kind==='wardrobe'?2.05:f.kind==='bookcase'?1.85:1.00);
  box(g,[0,h/2,0],[w,h,d],c);
  if(f.kind==='bookcase'){
   for(let j=0;j<4;j++){box(g,[0,(j+.25)*h/4,d*.48],[w*.96,.045,.10],c);for(let i=0;i<5;i++)box(g,[(i-2)*w*.15,(j+.59)*h/4,d*.50],[w*.095,h*.13,.045],['#8d7462','#67716b','#a99b84'][(i+j)%3]);}
  }else{const count=Math.max(2,Math.round(w/.55));for(let i=0;i<count;i++){const x=-w/2+(i+.5)*w/count;box(g,[x,h*.51,d/2+.011],[w/count-.018,h*.88,.022],c);box(g,[x+w/count*.26,h*.53,d/2+.034],[.026,.13,.035],'#6d6251');}}
 }
 else if(f.kind==='rug'){box(g,[0,.018,0],[w,.025,d],c);for(const side of [-1,1])box(g,[0,.032,side*d*.44],[w*.94,.006,.025],'#bd9b79');}
 else if(f.kind==='fireplace'){box(g,[0,.64,0],[w,1.28,d],c);box(g,[0,.38,d*.505],[w*.61,.53,.035],'#3b3330');box(g,[0,1.32,0],[w+.11,.10,d+.08],'#7f6652');}
 else box(g,[0,(f.height||1.8)/2,0],[w,f.height||1.8,d],c);
 return g;
}
function spiral(group,s,y){
 const [cx,cz]=s.center,r=s.diameter/2,count=Math.max(13,Math.round(s.rise/.18));
 for(let i=0;i<count;i++){const a=i*Math.PI*1.8/count,b=(i+1)*Math.PI*1.8/count;
 const ray=(t,d)=>[cx+Math.cos(t)*d,cz+Math.sin(t)*d];
 polygon(group,[ray(a,.07),ray(a,r),ray((a+b)/2,r),ray(b,r),ray(b,.07)],y+s.rise*(i+1)/count,.055,'#988671');}
 beam(group,[cx,y,cz],[cx,y+s.rise+.1,cz],'#746b62',.055);
}
function stairs(group,s,y){const a=s.a,b=s.b,len=Math.hypot(b[0]-a[0],b[1]-a[1]),n=s.steps||Math.max(3,Math.round(s.rise/.17)),h=s.rise/n,unit=len/n,start=s.startRise||0;for(let i=0;i<n;i++){const t=(i+.5)/n,height=start+(i+1)*h,center=[a[0]+(b[0]-a[0])*t,y+height/2,a[1]+(b[1]-a[1])*t];const o=box(group,center,[s.width||.9,height,unit+.006],s.color||data.colors?.stairs||'#b2a58a');o.rotation.y=Math.atan2(b[0]-a[0],b[1]-a[1]);}}
const levels=data.levels.map(level=>{const root=new THREE.Group(),low=new THREE.Group(),high=new THREE.Group(),furniture=new THREE.Group();scene.add(root);root.add(low,high,furniture);for(const surface of level.surfaces||[{points:level.outline}])polygon(low,surface.points,level.y,level.slabThickness??.16,surface.color||data.colors?.floor||'#b7a88f',surface.holes||level.holes||[],surface.finish);for(const w of level.walls){const wallHeight=w.height??level.height??2.7;wall(low,w,level.y,Math.min(.76,wallHeight));const wHigh={...w,openings:(w.openings||[]).map(o=>{const sill=Math.max(0,(o.sill||0)-.76);return {...o,sill,height:Math.max(0,(o.sill||0)+(o.height||2.05)-.76-sill)};})};if(wallHeight>.76)wall(high,wHigh,level.y+.76,wallHeight-.76);}for(const f of level.furniture||[])furnishing(furniture,f,level.y);for(const s of level.stairs||[])stairs(low,s,level.y);for(const s of level.spiralStairs||[])spiral(low,s,level.y);for(const t of level.stairTreads||[])polygon(low,t.points,level.y+t.rise,t.thickness||.10,t.color||data.colors?.stairs);for(const item of level.components||[]){if(item.points)polygon(low,item.points,level.y+(item.rise||0),item.thickness||.1,item.color);else if(item.kind==='glass'){const o=box(low,[item.center[0],level.y+item.center[1],item.center[2]],item.size,item.color);o.material=new THREE.MeshStandardMaterial({color:item.color,transparent:true,opacity:.24,roughness:.15});o.castShadow=false;}else if(item.kind==='gable'){
 const shape=new THREE.Shape([new THREE.Vector2(-item.z0,item.eave),new THREE.Vector2(-item.z1,item.eave),new THREE.Vector2(-(item.z0+item.z1)/2,item.peak)]);
 const gable=mesh(new THREE.ExtrudeGeometry(shape,{depth:item.thickness,bevelEnabled:false}),mat(item.color),high);
 gable.rotation.y=Math.PI/2;gable.position.set(item.x-item.thickness/2,level.y,0);
}else if(item.kind==='beam')beam(low,[item.a[0],level.y+item.a[1],item.a[2]],[item.b[0],level.y+item.b[1],item.b[2]],item.color,item.radius);else box(low,[item.center[0],level.y+item.center[1],item.center[2]],item.size,item.color);}return {root,low,high,furniture,definition:level};});
const outside=new THREE.Group(),roof=new THREE.Group();scene.add(outside,roof);
for(const item of data.exteriors||[]){if(item.points)polygon(outside,item.points,item.y??-.20,item.thickness||.13,item.color||'#858b66');else if(item.kind==='box'){const object=box(outside,item.center,item.size,item.color);object.rotation.y=item.rotationY||0;}}
for(const r of data.roofs||[]){const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(r.vertices.flat(),3));const indices=r.indices||r.vertices.slice(2).flatMap((_,i)=>[0,i+1,i+2]);geo.setIndex(indices);geo.computeVertexNormals();const obj=mesh(geo,new THREE.MeshStandardMaterial({color:r.color||data.colors?.roof||'#97684a',roughness:.9,side:THREE.DoubleSide}),roof);obj.receiveShadow=true;}
function batch(group){
 group.updateWorldMatrix(true,true);const inv=group.matrixWorld.clone().invert(),sets=new Map(),objects=[];
 group.traverse(o=>{if(!o.isMesh||Array.isArray(o.material)||o.material.transparent)return;const k=o.material.uuid+'_'+(o.userData.category||'')+'_'+o.castShadow;
 if(!sets.has(k))sets.set(k,[]);sets.get(k).push(o);});
 for(const meshes of sets.values()){if(meshes.length<2)continue;
  const pieces=meshes.map(o=>{let g=o.geometry.index?o.geometry.toNonIndexed():o.geometry.clone();g.applyMatrix4(new THREE.Matrix4().multiplyMatrices(inv,o.matrixWorld));return g;});
  const combined=mergeGeometries(pieces);pieces.forEach(g=>g.dispose());if(!combined)continue;
  const m=new THREE.Mesh(combined,meshes[0].material);m.userData={...meshes[0].userData};m.castShadow=meshes[0].castShadow;m.receiveShadow=true;objects.push(m);
  for(const o of meshes){o.removeFromParent();o.geometry.dispose();}
 }for(const object of objects)group.add(object);
}
for(const level of levels){batch(level.low);batch(level.high);batch(level.furniture);}batch(outside);batch(roof);
const hemi=new THREE.HemisphereLight('#fff8ec','#938775',data.rendering?.hemisphereIntensity??1.85);scene.add(hemi);const sun=new THREE.DirectionalLight('#ffe5c3',data.rendering?.sunIntensity??2.3);scene.add(sun,sun.target);sun.position.set(-25,36,20);sun.castShadow=true;sun.shadow.mapSize.set(1024,1024);sun.shadow.bias=-.00012;sun.shadow.normalBias=.035;Object.assign(sun.shadow.camera,{left:-40,right:40,top:40,bottom:-40,near:1,far:120});
const allBox=new THREE.Box3();for(const lv of levels)if(!lv.definition.separate&&lv.definition.exteriorVisible!==false)allBox.expandByObject(lv.root);allBox.expandByObject(roof);allBox.expandByObject(outside);const size=allBox.getSize(new THREE.Vector3()),center=allBox.getCenter(new THREE.Vector3()),span=Math.max(size.x,size.z,8);controls.minDistance=span*.16;controls.maxDistance=span*8;
const defaultViews=[{label:data.exteriorLabel||'Esterno',level:null}];
if(data.coverage!=='exterior_only'){
 data.levels.forEach((level,i)=>{if(!level.exteriorOnly)defaultViews.splice(1,0,{label:level.label,level:i});});
}
const views=data.views?.length&&data.views.every(v=>v.level===null||Number.isInteger(v.level))?data.views:defaultViews;
function resize(){renderer.setSize(innerWidth,innerHeight,false);camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();if(planMode&&activeCamera.isOrthographicCamera){const h=activeCamera.userData.span/2;activeCamera.left=-h*camera.aspect;activeCamera.right=h*camera.aspect;activeCamera.top=h;activeCamera.bottom=-h;activeCamera.updateProjectionMatrix();}}
function perspective(){activeCamera=camera;planMode=false;controls.enabled=true;}
function setMode(index){mode=((index%views.length)+views.length)%views.length;perspective();const selected=views[mode].level;levels.forEach((lv,i)=>{lv.root.visible=selected===null?!lv.definition.separate&&lv.definition.exteriorVisible!==false:i===selected;lv.low.visible=true;lv.high.visible=selected===null;lv.furniture.visible=true;});roof.visible=selected===null;outside.visible=selected===null;renderer.shadowMap.needsUpdate=true;
 const boxView=selected===null?allBox:new THREE.Box3().setFromObject(levels[selected].root);const c=boxView.getCenter(new THREE.Vector3()),s=boxView.getSize(new THREE.Vector3()),d=Math.max(s.x,s.z,6)*Math.max(1,1/camera.aspect)*1.6;controls.target.set(c.x,selected===null?c.y:levels[selected].definition.y+.30,c.z);camera.up.set(0,1,0);const v=views[mode].camera;
 if(v){const target=v.target||controls.target.toArray();controls.target.fromArray(target);const dist=v.distance||d;camera.position.copy(controls.target).add(new THREE.Vector3(Math.sin(v.yaw)*Math.cos(v.pitch)*dist,Math.sin(v.pitch)*dist,Math.cos(v.yaw)*Math.cos(v.pitch)*dist));}
 else camera.position.set(c.x+d*(data.cameraX??.60),c.y+d*(data.cameraY??.68),c.z+d*(data.cameraZ??.75));controls.update();}
function top(){const i=views[mode].level;const b=i===null?allBox:new THREE.Box3().setFromObject(levels[i].root),c=b.getCenter(new THREE.Vector3()),s=b.getSize(new THREE.Vector3());activeCamera=new THREE.OrthographicCamera(-1,1,1,-1,.01,300);activeCamera.userData.span=Math.max(s.z,s.x/camera.aspect)*1.12;activeCamera.position.set(c.x,Math.max(c.y+100,100),c.z);activeCamera.up.set(0,0,-1);activeCamera.lookAt(c.x,i===null?c.y:levels[i].definition.y,c.z);planMode=true;controls.enabled=false;resize();}
function plan(levelIndex,opts={}){setMode(views.findIndex(v=>v.level===levelIndex));levels[levelIndex].furniture.visible=false;top();if(opts.bounds){const b=opts.bounds;activeCamera.left=b[0];activeCamera.right=b[2];activeCamera.top=-b[1];activeCamera.bottom=-b[3];activeCamera.position.set(0,100,0);activeCamera.lookAt(0,0,0);activeCamera.updateProjectionMatrix();}return true;}
function geometry(){scene.updateMatrixWorld(true);const result=[];levels.forEach((lv,i)=>{for(const layer of [lv.low,lv.high])layer.traverse(o=>{if(o.isMesh&&o.userData.category==='wall'){const vertices=[];const attribute=o.geometry.attributes.position;for(let j=0;j<attribute.count;j++){const v=new THREE.Vector3().fromBufferAttribute(attribute,j).applyMatrix4(o.matrixWorld);vertices.push(v.toArray());}result.push({level:i,kind:'wall',vertices});}});});return result;}
canvas.addEventListener('contextmenu',e=>e.preventDefault());canvas.addEventListener('pointerdown',()=>{if(planMode)perspective();});
let lastTouch=0,lastTap=0,lastTapPoint=null,press=null,multi=false;const touchIds=new Set();
canvas.addEventListener('pointerdown',e=>{if(e.pointerType==='touch'){lastTouch=performance.now();touchIds.add(e.pointerId);if(touchIds.size>1){multi=true;lastTap=0;}press={x:e.clientX,y:e.clientY,at:e.timeStamp,moved:false};}});
canvas.addEventListener('pointermove',e=>{if(e.pointerType==='touch'&&press&&Math.hypot(e.clientX-press.x,e.clientY-press.y)>=7){press.moved=true;lastTap=0;lastTapPoint=null;}});
canvas.addEventListener('pointerup',e=>{if(e.pointerType==='touch'){const now=e.timeStamp;if(!multi&&press&&!press.moved&&Math.hypot(e.clientX-press.x,e.clientY-press.y)<7&&now-press.at>=0&&now-press.at<300){const near=lastTapPoint&&Math.hypot(e.clientX-lastTapPoint[0],e.clientY-lastTapPoint[1])<24;if(lastTap&&near&&now-lastTap>=0&&now-lastTap<350){setMode(mode+1);lastTap=0;lastTapPoint=null;}else{lastTap=now;lastTapPoint=[e.clientX,e.clientY];}}else{lastTap=0;lastTapPoint=null;}touchIds.delete(e.pointerId);if(!touchIds.size){multi=false;press=null;}lastTouch=performance.now();}});
canvas.addEventListener('pointercancel',e=>{touchIds.delete(e.pointerId);press=null;lastTap=0;lastTapPoint=null;multi=false;});canvas.addEventListener('dblclick',e=>{if(e.sourceCapabilities?.firesTouchEvents||e.pointerType==='touch')return;if(performance.now()-lastTouch>550)setMode(mode+1);});
addEventListener('keydown',e=>{if(e.target instanceof HTMLElement&&e.target.closest('input,textarea,select,[contenteditable]'))return;const k=e.key.toLowerCase();if(k==='r'){e.preventDefault();setMode(mode+1);}else if(k==='t'){e.preventDefault();top();}else if(k==='0'||k==='home'){e.preventDefault();setMode(0);}else if(/^[1-9]$/.test(k)&&+k<=views.length){e.preventDefault();setMode(+k-1);}else if(['arrowleft','arrowright','arrowup','arrowdown','+','=','-'].includes(k)){e.preventDefault();perspective();const offset=camera.position.clone().sub(controls.target),s=new THREE.Spherical().setFromVector3(offset);if(k==='arrowleft')s.theta+=.12;if(k==='arrowright')s.theta-=.12;if(k==='arrowup')s.phi=Math.max(.05,s.phi-.1);if(k==='arrowdown')s.phi=Math.min(Math.PI/2-.03,s.phi+.1);if(k==='+'||k==='=')s.radius*=.9;if(k==='-')s.radius*=1.1;s.radius=THREE.MathUtils.clamp(s.radius,controls.minDistance,controls.maxDistance);camera.position.copy(controls.target).add(new THREE.Vector3().setFromSpherical(s));controls.update();}});
addEventListener('resize',resize);canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();lost=true;document.body.dataset.render='lost';});canvas.addEventListener('webglcontextrestored',()=>location.reload());
window.__sceneControls={setMode,reset:()=>setMode(0),plan,top,geometry,pause:()=>paused=true,resume:()=>paused=false,camera:(yaw,pitch,d,target)=>{perspective();controls.target.fromArray(target||controls.target.toArray());camera.position.copy(controls.target).add(new THREE.Vector3(Math.sin(yaw)*Math.cos(pitch)*d,Math.sin(pitch)*d,Math.cos(yaw)*Math.cos(pitch)*d));controls.update();}};
resize();setMode(0);
function frame(){requestAnimationFrame(frame);if(paused||lost||document.hidden)return;if(!planMode)controls.update();renderer.render(scene,activeCamera);frames++;document.body.dataset.render='ready';const offset=camera.position.clone().sub(controls.target),s=new THREE.Spherical().setFromVector3(offset);window.__sceneState={ready:true,viewLabel:views[mode].label,frames,mode,viewCount:views.length,camera:{yaw:s.theta,pitch:Math.PI/2-s.phi,distance:s.radius,target:controls.target.toArray()},orthographic:planMode,geometrySource:data.geometrySource||'source-traced',webgl:renderer.getContext().getParameter(renderer.getContext().VERSION)};}
frame();
