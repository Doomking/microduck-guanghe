const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');const {JSDOM}=require(process.env.MICRODUCK_JSDOM_PATH||'jsdom');
const root=path.resolve(__dirname,'../..');
(async()=>{
 const dom=new JSDOM(fs.readFileSync(path.join(root,'static/index.html'),'utf8'),{url:'http://localhost:48305/',pretendToBeVisual:true});
 for(const name of ['window','document','localStorage','HTMLElement','Element','CustomEvent','Event','Node','HTMLInputElement','HTMLSelectElement','getComputedStyle','requestAnimationFrame','cancelAnimationFrame'])global[name]=['getComputedStyle','requestAnimationFrame','cancelAnimationFrame'].includes(name)?dom.window[name].bind(dom.window):dom.window[name];
 window.HTMLCanvasElement.prototype.getContext=()=>({clearRect(){},fillRect(){},beginPath(){},moveTo(){},lineTo(){},stroke(){},fillText(){},measureText(){return {width:12};}});
 const ids=[20,21,22,23,24,30,31,32,33,34,10,11,12,13,14],writes=[];
 let order={schema:'feetech-read-order/v1',revision:0,applied_revision:0,applied:[200,...ids],desired:[200,...ids],pending:false,persistence:'robot_config',saved_revision:0};
 const stats={classification:'exclusive-v2',session:'current-session',by_id:Object.fromEntries([...ids,200].map(i=>[i,{missing:0,timeout:0}]))};
 global.fetch=async(url,opts)=>{
  if(url==='/api/service/read-order/status')return {ok:true,json:async()=>({report:{read_order:structuredClone(order),device_communication:stats}})};
  if(url==='/api/service/read-order'){
   const body=JSON.parse(opts.body);writes.push(body);const applied=[...order.applied.filter(i=>i!==body.id),body.id];
   order={...order,revision:order.revision+1,applied_revision:order.revision+1,saved_revision:order.revision+1,applied,desired:applied};
   return {ok:true,json:async()=>({accepted:true,read_order:structuredClone(order)})};
  }
  return {ok:true,json:async()=>({available:false,models:[],job:null})};
 };
 const {ServicePanel}=await import(pathToFileURL(path.join(root,'static/service.js')));
 const cfg={service_enabled:true,connection_ui:false,control_token:'test',ids,labels:ids.map(i=>'关节 '+i),names:ids.map(i=>'joint_'+i)};
 const panel=new ServicePanel(cfg,()=>{}),inspection=panel.inspection,control=inspection.readOrderControl;
 const snapshot={channels:{bus:{status:'live'}},service_sample_fresh:false,servos:[],bus:{build:'1fa843-feetech-ft6-control.126',mode:'commissioning',device_communication:stats}};
 for(const count of [0,10]){stats.by_id[10].timeout=count;inspection.render(snapshot);assert(control.buttons.get(10).disabled);await control.move(10);}
 assert.equal(writes.length,0);stats.by_id[10].timeout=11;inspection.render(snapshot);await control.read();
 assert.equal(control.buttons.size,15);assert(!control.buttons.has(200));assert(!control.buttons.get(10).disabled);
 await control.move(10);assert.equal(writes.length,1);assert.deepEqual(writes[0],{id:10,session:'current-session',revision:0});
 assert(control.line.textContent.endsWith('→10'));assert(control.buttons.get(10).disabled);
 assert(!control.line.textContent.includes('\n'));assert(inspection.$('feedback').textContent.includes('已保存'));
 for(const options of [{offline:true},{replay:true}]){inspection.render(snapshot,options);assert(control.buttons.get(11).disabled);}
 assert.equal(document.querySelectorAll('.inspection-device .inspection-order-feedback').length,0);
 const report={passed:true,originalV302PanelMounted:true,strictGreaterThan10:true,oneMoveRequest:true,actualOrderDisplayed:true,
   imuFixedFirst:true,commonCompactFeedback:true,offlineReplayDisabled:true,browserPixelsTested:false,physicalHardwareTested:false};
 fs.writeFileSync(path.join(__dirname,'ui-results.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));dom.window.close();
})().catch(e=>{console.error(e.stack);process.exit(1);});
