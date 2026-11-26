const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),vm=require('node:vm');
const {pathToFileURL}=require('node:url');
const {JSDOM}=require(process.env.MICRODUCK_JSDOM_PATH||'jsdom');
const APP=path.resolve(__dirname,'../..'),read=n=>fs.readFileSync(path.join(APP,n),'utf8');
(async()=>{
 const dom=new JSDOM(read('static/index.html'),{url:'http://localhost:48301/',pretendToBeVisual:true});
 for(const name of ['window','document','localStorage','HTMLElement','Element','CustomEvent','Event','Node','HTMLInputElement','HTMLSelectElement','getComputedStyle','requestAnimationFrame','cancelAnimationFrame']){
  global[name]=['getComputedStyle','requestAnimationFrame','cancelAnimationFrame'].includes(name)?dom.window[name].bind(dom.window):dom.window[name];
 }
 for(const link of document.querySelectorAll('link[rel="stylesheet"]')){
  const style=document.createElement('style');style.textContent=read('static/'+link.getAttribute('href').slice(1));document.head.append(style);
 }
 window.HTMLCanvasElement.prototype.getContext=()=>({clearRect(){},fillRect(){},beginPath(){},moveTo(){},lineTo(){},stroke(){},fillText(){},measureText(){return {width:12};}});
 let writes=0;global.fetch=async(url,options)=>{if(options?.method&&options.method!=='GET')writes++;return {ok:true,status:200,json:async()=>({available:false,models:[],job:null})};};
 const load=n=>import(pathToFileURL(path.join(APP,'static/'+n)));
 const [{ServicePanel},{FourPageConsole},{DuckView},{CalibrationViewPanel},T,{parseDuck},{REFERENCE_IDS,referencePose},{bodyMarkerLayout}]=await Promise.all([
  load('service.js'),load('four-pages.js'),load('duck.js'),load('calibration-view.js'),load('vendor/three.module.min.js'),load('pose.js'),load('calibration-reference.js'),load('viewport-markers.js')]);
 const cfg={service_enabled:true,connection_ui:false,control_token:'model-view-test',ids:[...REFERENCE_IDS],labels:REFERENCE_IDS.map(i=>'关节 '+i),names:REFERENCE_IDS.map(i=>'joint_'+i),ssh_target:'fixture'};
 const pages=Object.create(FourPageConsole.prototype),servicePanel=new ServicePanel(cfg,()=>{});
 Object.assign(pages,{cfg,servicePanel,controls:{suspend(){}},state:{available:false},permissions:Object.fromEntries(['numbering','hardware','calibration','robot'].map(k=>[k,{browsable:true}])),page:null,rowTargets:new Map(),numberingCardHeight:null});
 pages.mount();pages.syncPositionStream=()=>{};pages.paintWorkspaceModes=()=>{};pages.openFirmwarePower=()=>{};pages.feedback=()=>{};
 const view=new DuckView(),bytes=fs.readFileSync(path.join(APP,'static/assets/duck-visual.bin'));
 view.model=parseDuck(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength));
 view.geometry=view.model.meshes.map(m=>{
  const g=new T.BufferGeometry();g.setAttribute('position',new T.BufferAttribute(m.vertices,3));g.setAttribute('normal',new T.BufferAttribute(m.normals,3));g.setIndex(new T.BufferAttribute(m.indices,1));return g;
 });
 view.actual=view.build(false);view.ghost=view.build(true);view.ghost.root.visible=false;
 view.camera=new T.PerspectiveCamera(37,1,.005,20);view.camera.up.set(0,0,1);view.controls={target:new T.Vector3(),update(){view.camera.lookAt(this.target);}};
 new CalibrationViewPanel(view);
 await new Promise(resolve=>setImmediate(resolve));writes=0; // Exclude the constructor's firmware metadata verification.
 const app=read('static/app.js'),begin=app.indexOf('function render(s,addHistory=true){'),end=app.indexOf('\nfunction renderTof(',begin);
 assert(begin>=0&&end>begin);
 const $=id=>document.getElementById(id),finite=Number.isFinite;
 const context={document,performance,Date,Math,console,duck:view,shown:null,apiOkay:true,replay:null,cfg:{connection_ui:false,baseline:'590b986'},
  fourPages:{page:'calibration',state:{},receivedAt:0,withMaintenance:s=>s,render(){}},sshConnection:null,controls:null,wifiPanel:null,servicePanel:null,
  history:[],historyFrame:s=>s,sourceLive:(s,n)=>s.channels?.[n]?.status==='live',modeDisplay(){},
  finite,fmt:(v,d=1)=>finite(v)?v.toFixed(d):'—',vec:v=>JSON.stringify(v),radians:v=>finite(v)?v*180/Math.PI:null,
  text:(id,value)=>{const el=$(id);assert(el,id);el.textContent=value;},$,
  badge(){},loopHz:()=>50,statusNames:{live:'实时'},messageZh:v=>v||'',renderTof(){},renderSystem(){},renderMotors(){},renderDiagnostics(){},drawHistory(){},
  connectionNotice:()=>({hidden:true,tone:'neutral',message:''}),connectionWorkspaceState:()=>({})};
 vm.createContext(context);vm.runInContext(app.slice(begin,end)+'\nglobalThis.renderSnapshot=render;',context);
 const snapshot={mode:'service',at:1,service_sample_fresh:true,connection:{active:true,connected:true},channels:{state:{status:'live'}},state:{odom:{yaw:0}},
  imu:{status:'live',ready:true,mount_verified:true,gravity:[0,0,-1],gyro:[0,0,0],quat:[1,0,0,0]},
  servos:REFERENCE_IDS.map((id,i)=>({id,status:'live',calibrated:true,angle_deg:i+1,position_raw:2048,temperature_c:30,voltage_v:8}))};
 const toolbar=document.querySelector('.pose-reference-toolbar'),twin=pages.twin,checks=[];
 for(const page of ['calibration','robot','calibration','robot']){
  pages.open(page,{automatic:true});context.fourPages.page=page;
  assert.equal(twin.closest('.task-page').id,'page-'+page);assert.equal(getComputedStyle(toolbar).display,'block');
  for(const mode of ['zero','home']){
   $('pose-reference-'+mode).click();assert.equal(view.referenceMode,mode);
   for(let tick=0;tick<3;tick++)context.renderSnapshot({...snapshot,at:tick+1},false);
   assert.equal(view.referenceMode,mode,`${page}: telemetry must not reset ${mode}`);
   assert.deepEqual(view.referenceJoints,referencePose(mode));
   assert(view.measuredJoints.some(x=>x!==0),'measured feedback continues underneath reference');
   assert.equal($('pose-reference-'+mode).getAttribute('aria-pressed'),'true');
   assert($('pose-label').textContent.includes(mode==='zero'?'零位':'HOME'));
   assert($('pose-hud').hidden);assert(!view.ghost.root.visible);
   checks.push(page+':'+mode);
  }
  $('pose-reference-measured').click();assert.equal(view.referenceMode,'measured');assert(!$('pose-hud').hidden);
  snapshot.servos.forEach((row,i)=>assert(Math.abs(view.measuredJoints[i]-row.angle_deg*Math.PI/180)<1e-12));
  view.selectJoint(9);assert($('pose-reference-positive').disabled&&$('pose-reference-negative').disabled);view.selectJoint(0);
 }
 assert.equal(writes,0,'reference buttons must not send any robot writes');
 assert.equal(document.querySelectorAll('#pose-reference-zero').length,1);assert.equal(document.querySelectorAll('#pose-reference-home').length,1);
 const stage=twin.querySelector('.twin-stage'),legend=twin.querySelector('.axis-legend'),footer=twin.querySelector('.twin-footer');
 assert.equal(stage.querySelector('.axis-legend'),null);assert.equal(legend.parentElement.className,'twin-coordinate-legend');
 assert.equal(legend.parentElement.nextElementSibling,footer);assert.equal(getComputedStyle(legend).position,'static');
 assert.equal(getComputedStyle(stage).overflow,'hidden');assert.equal(getComputedStyle($('duck-canvas')).overflow,'hidden');
 const intersect=(a,b)=>a.left<b.left+b.width&&a.left+a.width>b.left&&a.top<b.top+b.height&&a.top+a.height>b.top;
 let markerCases=0;
 const mark=(x,y,z=0)=>({point:{x,y,z},width:102,height:24});
 for(const [width,height] of [[240,160],[360,260],[720,500]])for(const [x,y] of [[0,0],[-1,-1],[1,-1],[0,1]]){
  const positions=bodyMarkerLayout(width,height,[mark(x,y),mark(x,y)]);
  assert(positions.every(Boolean));assert(!intersect(positions[0].box,positions[1].box));
  for(const {box} of positions){assert(box.left>=0&&box.top>=0&&box.left+box.width<=width&&box.top+box.height<=height);}
  markerCases++;
 }
 const blocked={left:95,top:60,width:110,height:40},positions=bodyMarkerLayout(300,180,[mark(0,0),mark(0,0)],[blocked]);
 assert(positions.every(Boolean));for(const {box} of positions)assert(!intersect(box,blocked));markerCases++;
 assert.deepEqual(bodyMarkerLayout(300,180,[mark(0,0)],[{left:0,top:0,width:300,height:180}]),[null]);
 assert.deepEqual(bodyMarkerLayout(300,180,[mark(2,0),mark(0,0,2),mark(NaN,0)]),[null,null,null]);
 assert.deepEqual(bodyMarkerLayout(0,0,[mark(0,0)]),[null]);markerCases+=3;
 const container=$('duck-canvas');view.container=container;view.bodyAxes=new T.AxesHelper(.055);
 Object.defineProperties(container,{clientWidth:{get:()=>360},clientHeight:{get:()=>260}});
 container.getBoundingClientRect=()=>({left:0,top:0,width:360,height:260});
 view.sideTags=['左侧 · 20–24','右侧 · 10–14'].map(text=>{
  const tag=document.createElement('span');tag.className='robot-side-tag';tag.textContent=text;
  Object.defineProperties(tag,{offsetWidth:{get:()=>102},offsetHeight:{get:()=>24}});container.append(tag);return tag;
 });
 view.camera.aspect=360/260;view.camera.updateProjectionMatrix();
 const cameraChecks=[];
 for(const angle of ['front','back','left','side','top']){
  view.view(angle);view.updateBodyMarkers();const boxes=[];
  for(const tag of view.sideTags)if(!tag.hidden){
   const box={left:parseFloat(tag.style.left)-51,top:parseFloat(tag.style.top)-12,width:102,height:24};
   assert(box.left>=0&&box.top>=0&&box.left+box.width<=360&&box.top+box.height<=260);boxes.push(box);
  }
  assert.equal(boxes.length,2,'both body labels should fit '+angle);assert(!intersect(boxes[0],boxes[1]));cameraChecks.push(angle);
 }
 const report={passed:true,referenceViews:checks,actualAppRender:true,actualModelTransforms:true,referenceWrites:writes,measuredUpdatesRetained:true,
  markerCases,cameraChecks,separateFooterLegend:true,duplicateIds:false,browserPixelsTested:false,webglPixelsTested:false,
  limitation:'DOM/CSS, actual model CPU transforms, telemetry rendering and marker placement verified. Browser and WebGL pixels were not tested in this run.'};
 await new Promise(resolve=>setImmediate(resolve));
 fs.writeFileSync(path.join(__dirname,'results.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));dom.window.close();
})().catch(error=>{console.error(error.stack);process.exit(1);});
