const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {JSDOM}=require(process.env.MICRODUCK_JSDOM_PATH||'jsdom');
const {pathToFileURL}=require('node:url');
const APP=path.resolve(__dirname,'../..'),ROOT=APP;
(async()=>{
 const dom=new JSDOM(fs.readFileSync(path.join(APP,'static/index.html'),'utf8'),{url:'http://localhost:48299/',pretendToBeVisual:true});
 for(const name of ['window','document','localStorage','HTMLElement','Element','CustomEvent','Event','HTMLInputElement','HTMLSelectElement','Node','getComputedStyle','requestAnimationFrame','cancelAnimationFrame'])global[name]=typeof dom.window[name]==='function'&&['getComputedStyle','requestAnimationFrame','cancelAnimationFrame'].includes(name)?dom.window[name].bind(dom.window):dom.window[name];
 window.HTMLCanvasElement.prototype.getContext=()=>({clearRect(){},fillRect(){},beginPath(){},moveTo(){},lineTo(){},stroke(){},fillText(){},measureText(){return {width:12};}});
 global.fetch=async()=>({ok:true,status:200,json:async()=>({available:false,models:[],job:null})});
 const {ServicePanel}=await import(pathToFileURL(path.join(APP,'static/service.js')));
 const {FourPageConsole}=await import(pathToFileURL(path.join(APP,'static/four-pages.js')));
 const ids=[20,21,22,23,24,30,31,32,33,34,10,11,12,13,14],cfg={service_enabled:true,connection_ui:false,control_token:'layout-test',ids,labels:ids.map(i=>'关节 '+i),names:ids.map(i=>'joint_'+i),ssh_target:'fixture'};
 const p=Object.create(FourPageConsole.prototype),servicePanel=new ServicePanel(cfg,()=>{});
 Object.assign(p,{cfg,servicePanel,controls:{suspend(){}},state:{available:false},permissions:Object.fromEntries(['numbering','hardware','calibration','robot'].map(k=>[k,{browsable:true}])),page:null,rowTargets:new Map(),numberingCardHeight:null});
 p.mount();p.syncPositionStream=()=>{};p.paintWorkspaceModes=()=>{};p.openFirmwarePower=()=>{};p.feedback=()=>{};
 const imu=p.imuPanel,curve=p.jointChart;assert(imu&&curve);const checks=[];
 for(let pass=0;pass<4;pass++)for(const mode of ['calibration','robot','hardware','numbering']){
  assert.equal(p.open(mode,{automatic:true}),true);
  if(mode==='calibration'||mode==='robot'){
   const host=mode==='calibration'?p.calibrationCurveHost:p.robotCurveHost;
   assert.deepEqual([...host.children],[imu,curve]);
   assert.equal(host.classList.contains('joint-observation-row'),true);
   assert.equal(host.closest('.task-page').id,'page-'+mode);
   assert.equal(document.getElementById('page-'+mode).hidden,false);
   const snapshot={imu:{status:'live',roll_deg:12,pitch_deg:-8,gravity:[.1,.2,.97]}};
   assert.equal(p.withMaintenance(snapshot),snapshot,'service pages keep the original telemetry source');
   if(mode==='calibration')assert.equal(document.getElementById('calibration-shared').firstElementChild,p.motors);
  } else if(mode==='hardware'){
   assert.equal(imu.parentElement,p.hardwareImuHost);assert.equal(p.hardwareImuHost.firstElementChild,imu);
   assert(imu.querySelector('#board-imu-start'));assert(imu.querySelector('#board-imu-stop'));
  }
  for(const id of ['imu-badge','horizon','gravity-chart','joint-chart','dial-clip'])assert.equal(document.querySelectorAll('#'+id).length,1,id);
  checks.push({pass,mode,imuParent:imu.parentElement.id||imu.parentElement.className,curveParent:curve.parentElement.id});
 }
 const css=fs.readFileSync(path.join(APP,'static/four-pages.css'),'utf8');assert(css.includes('.joint-observation-row{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))'));
 assert(css.includes('.joint-observation-row>#board-imu-panel .imu-test-toolbar{display:none}'));
 const out=__dirname;fs.mkdirSync(out,{recursive:true});
 fs.writeFileSync(path.join(out,'results.json'),JSON.stringify({passed:true,modeTransitions:checks.length,checks,liveComponentsReused:true,duplicateIds:false,serviceTelemetrySourceUnchanged:true,hardwareButtonsPreserved:true,cssTwoColumns:true,pixelLayoutTested:false,pixelTestLimit:'Local Chromium launch was blocked by workspace UNIX socket restrictions.'},null,2)+'\n');
 await new Promise(resolve=>setImmediate(resolve));console.log(JSON.stringify({passed:true,modeTransitions:checks.length,sharedImu:true,sharedCurve:true,uniqueIds:true,hardwareButtonsPreserved:true}));dom.window.close();
})().catch(e=>{console.error(e.stack);process.exit(1);});
