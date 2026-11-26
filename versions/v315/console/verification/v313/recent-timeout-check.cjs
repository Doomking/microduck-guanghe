const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');
const {JSDOM}=require(process.env.MICRODUCK_JSDOM_PATH||'jsdom');
const root=path.resolve(process.env.MICRODUCK_CONSOLE_ROOT||path.join(__dirname,'../..'));
const settle=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 const dom=new JSDOM(fs.readFileSync(path.join(root,'static/index.html'),'utf8'),{url:'http://localhost:48305/',pretendToBeVisual:true});
 for(const name of ['window','document','localStorage','HTMLElement','Element','CustomEvent','Event','Node','HTMLInputElement','HTMLSelectElement','getComputedStyle','requestAnimationFrame','cancelAnimationFrame'])global[name]=['getComputedStyle','requestAnimationFrame','cancelAnimationFrame'].includes(name)?dom.window[name].bind(dom.window):dom.window[name];
 window.HTMLCanvasElement.prototype.getContext=()=>({clearRect(){},fillRect(){},beginPath(){},moveTo(){},lineTo(){},stroke(){},fillText(){},measureText(){return {width:12};}});
 let clock=0;Object.defineProperty(globalThis,'performance',{configurable:true,value:{now:()=>clock}});
 const ids=[20,21,22,23,24,30,31,32,33,34,10,11,12,13,14],writes=[];
 let calls=0,unsupported=false;
 let order={revision:0,applied_revision:0,applied:[200,...ids],desired:[200,...ids],pending:false,saved_revision:0};
 const stats={classification:'exclusive-v2',session:'session-one',by_id:Object.fromEntries([...ids,200].map(i=>[i,{missing:0,timeout:0}]))};
 global.fetch=async(url,opts)=>{
  if(url==='/api/service/read-order/status'){
   calls++;
   if(unsupported)return {ok:false,json:async()=>({error:'invalid bus command: unknown variant `read-order-status`'})};
   return {ok:true,json:async()=>({report:{read_order:structuredClone(order),device_communication:stats}})};
  }
  if(url==='/api/service/read-order'){
   const body=JSON.parse(opts.body);writes.push(body);
   const applied=[...order.applied.filter(i=>i!==body.id),body.id];
   order={...order,revision:order.revision+1,applied_revision:order.revision+1,saved_revision:order.revision+1,applied,desired:applied};
   return {ok:true,json:async()=>({accepted:true,read_order:structuredClone(order)})};
  }
  return {ok:true,json:async()=>({available:false,models:[],job:null})};
 };
 const {ServicePanel}=await import(pathToFileURL(path.join(root,'static/service.js')));
 const cfg={service_enabled:true,connection_ui:false,control_token:'test',ids,labels:ids.map(i=>'关节 '+i),names:ids.map(i=>'joint_'+i)};
 const panel=new ServicePanel(cfg,()=>{}),inspection=panel.inspection,control=inspection.readOrderControl;
 const snapshot={channels:{bus:{status:'live'}},service_sample_fresh:false,servos:[],bus:{mode:'commissioning',device_communication:stats,
   error:'Feetech Sync Read missing IDs [10]',last_failure:{read:4,error:'Feetech Sync Read missing IDs [10]'}}};
 stats.by_id[10].last_timeout_read=123;stats.by_id[10].last_timeout_elapsed_us=20_080;
 stats.by_id[12].last_timeout_read=456;stats.by_id[12].last_timeout_elapsed_us=30_125;
 stats.last_trace={address:56,length:15,request_sent:true,missing_ids:[],elapsed_us:1_234};
 inspection.render(snapshot);await settle();assert.equal(calls,1,'one read on connection');
 assert(inspection.cells.get(10).detail.textContent.includes('最近超时：第 123 次采集 · 20.080 ms'));
 assert(inspection.cells.get(12).detail.textContent.includes('最近超时：第 456 次采集 · 30.125 ms'));
 stats.last_trace.elapsed_us=2_345;inspection.render(snapshot);
 assert(inspection.cells.get(10).detail.textContent.includes('20.080 ms'));
 assert(inspection.cells.get(12).detail.textContent.includes('30.125 ms'));
 assert(!inspection.cells.get(200).detail.textContent.includes('最近超时：'));
 
 assert.equal(inspection.$('feedback').textContent,'','packet warnings stay on device cards');
 assert(!inspection.root.textContent.includes('各设备互斥统计'));
 for(let i=0;i<100;i++){clock+=3000;inspection.render(snapshot);await settle();}
 assert.equal(calls,1,'no repeated request during five minutes of live renders');
 for(const count of [0,10]){stats.by_id[10].timeout=count;inspection.render(snapshot);assert(control.buttons.get(10).disabled);await control.move(10);}
 assert.equal(writes.length,0);stats.by_id[10].timeout=11;inspection.render(snapshot);
 await control.move(10);assert.equal(writes.length,1);assert.equal(calls,2,'one read after a manual reorder');
 assert.deepEqual(writes[0],{id:10,session:'session-one',revision:0});
 assert(control.line.textContent.endsWith('→10'));assert(control.buttons.get(10).disabled);
 assert(inspection.$('feedback').textContent.includes('换序成功'));assert(!control.line.textContent.includes('\n'));
 assert(inspection.$('feedback').classList.contains('completed'),'successful reorder has green confirmation');
 assert(!inspection.$('feedback').textContent.includes('missing IDs'));
 assert(inspection.cells.get(10).detail.textContent.includes('11 次'),'device loss count remains visible');
 snapshot.service_operation={state:'running'};inspection.render(snapshot);snapshot.service_operation=null;inspection.render(snapshot);await settle();
 assert.equal(calls,2,'ordinary operations do not trigger order reads');
 for(let i=0;i<100;i++){clock+=3000;inspection.render(snapshot);await settle();}
 assert.equal(calls,2,'no background reads after reorder');
 snapshot.channels.bus.status='unavailable';inspection.render(snapshot);snapshot.channels.bus.status='live';inspection.render(snapshot);await settle();
 assert.equal(calls,3,'one fresh read on reconnection');
 unsupported=true;stats.session='old-firmware-session';inspection.render(snapshot);await settle();assert.equal(calls,4);
 for(let i=0;i<100;i++){clock+=3000;inspection.render(snapshot);await settle();}
 assert.equal(calls,4,'unsupported command is not repeatedly sent');
 assert(inspection.$('feedback').textContent.includes('换序接口未就绪'));
 unsupported=false;stats.session='new-firmware-session';inspection.render(snapshot);await settle();assert.equal(calls,5);
 assert(control.line.textContent.endsWith('→10'));
 for(const options of [{offline:true},{replay:true}]){inspection.render(snapshot,options);await settle();assert.equal(calls,5);assert(control.buttons.get(11).disabled);}
 assert.equal(control.buttons.size,15);assert(!control.buttons.has(200));
 const result={passed:true,oneReadPerConnection:true,noPeriodicRequests:true,noRetryLoopOnUnknownCommand:true,
  oneReadAfterManualReorder:true,ordinaryOperationsDoNotReadOrder:true,reconnectRefreshesOnce:true,
  greaterThanTenGatePreserved:true,actualOrderDisplayed:true,greenSuccessConfirmation:true,
  packetWarningsOnlyOnCards:true,verboseExplanationRemoved:true,perDeviceHistoricalMs:true,freshReadDoesNotOverwriteTimeoutMs:true,physicalHardwareTested:false};
 if(!process.env.MICRODUCK_CONSOLE_ROOT)fs.writeFileSync(path.join(__dirname,'timeout-results.json'),JSON.stringify(result,null,2)+'\n');
 console.log(JSON.stringify(result));dom.window.close();
})().catch(e=>{console.error(e.stack);process.exit(1);});
