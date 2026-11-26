import {controlFetch} from './control-session.js';
import {showFeedback} from './feedback.js';
import {ReadOrderControl} from './read-order-control.js';
import {acceptedLateRead} from './read-timing.js';

const finite=v=>typeof v==='number'&&Number.isFinite(v);
const fmt=(v,n=1)=>finite(v)?v.toFixed(n):'—';
const errorsOf=b=>b.errors_by_id||b.diagnostics?.missing_by_id||{};
const totalsOf=b=>{
  const t=b.native?.telemetry;
  return t&&finite(t.total_reads)&&finite(t.failed_reads)&&t.missing_by_id?t:null;
};
const deviceStatsOf=b=>b.device_communication?.by_id?b.device_communication:null;
// v107 counted deadline misses twice. Convert that documented legacy schema;
// older native totals do not contain enough evidence to split cumulative causes.
export const separatedCounts=(stats,id)=>{
  const d=stats?.by_id?.[id];if(!d)return null;
  return stats.classification==='exclusive-v2'?d:{missing:Math.max(0,d.missing-(d.timeout||0)),timeout:d.timeout};
};
const isLoop=b=>b.mode==='motion'&&finite(b.cycle);

// This panel only observes robot.busStatus. The manual endpoint enables a
// bounded console recording; neither path opens a bus or issues device reads.
export class DeviceInspection {
  constructor(cfg,root){
    this.cfg=cfg;this.root=root;this.manual=false;this.pending=false;this.base=null;this.cells=new Map();this.s=null;this.options={};
    this.$=id=>root.querySelector('#inspection-'+id);
    for(const [i,id] of [...cfg.ids,200].entries()){
      const cell=document.createElement('div'),number=document.createElement('b'),name=document.createElement('span'),detail=document.createElement('small');
      cell.className='inspection-device';number.textContent=id;name.textContent=id===200?'IMU':cfg.labels[i];detail.textContent='未检测';
      cell.dataset.id=id;cell.append(number,name,detail);this.$('devices').append(cell);this.cells.set(id,{cell,detail});
    }
    this.$('start').onclick=()=>this.toggle(true);this.$('stop').onclick=()=>this.toggle(false);
    this.readOrderControl=new ReadOrderControl(cfg,root,this.cells,()=>this.paint());
    window.addEventListener('pagehide',()=>{if(this.manual)this.toggle(false,true);});
  }
  async toggle(enabled,keepalive=false){
    if(this.pending||enabled&&this.$('start').disabled)return;
    const b=this.s?.bus||{};
    const base=enabled?{session:b.session,cycle:b.total_cycles,failures:b.total_communication_failures,errors:{...errorsOf(b)}}:null;
    this.pending=true;this.paint();
    try{
      const response=await controlFetch('/api/inspection',{method:'POST',headers:{'Content-Type':'application/json','X-Control-Token':this.cfg.control_token},body:JSON.stringify({enabled}),keepalive});
      if(!response.ok)throw Error('检测状态未保存，请重试');
      this.manual=enabled;if(enabled){this.base=base;this.summary='';this.lastLoopFailure=null;this.autoStopKey='';}
      this.requestError='';
    }catch(error){this.requestError=error.message;}
    finally{this.pending=false;this.paint();}
  }
  render(s,options={}){this.s=s;this.options=options;this.paint();}
  paint(){
    if(!this.s)return;
    const s=this.s,b=s.bus||{},options=this.options,loop=isLoop(b);
    this.readOrderControl.render(s,options);
    const displayOnly=options.replay||options.offline;
    const live=s.channels?.bus?.status==='live'&&!options.offline;
    const counters=finite(b.total_cycles)&&finite(b.total_communication_failures);
    this.$('start').disabled=!!(loop||this.manual||this.pending||displayOnly||!live||!counters);
    this.$('stop').disabled=!this.manual||this.pending||!!displayOnly;
    const context=options.replay?'历史回放':!live?'反馈已中断':'';
    this.$('source').textContent=loop?'运动循环 · 自动接入':this.manual?'手动检测':'手动检测 · 待启动';
    this.$('source').className='badge '+(context?'warn':loop?'inspection-auto':'neutral');
    // A mode change ends the old manual interval; never subtract counters from
    // two robotd processes. Loop observation continues without an API start.
    const stopKey=`${b.mode}:${b.session}`;
    if(this.manual&&(loop||b.session!==this.base?.session||b.total_cycles<this.base?.cycle)&&!displayOnly&&!this.pending&&this.autoStopKey!==stopKey){
      this.autoStopKey=stopKey;this.toggle(false);return;
    }
    if(loop){
      if(!this.wasLoop)this.summary='';
      const totals=totalsOf(b),session=totals?.session;
      if(this.loopCycle===undefined||b.cycle<this.loopCycle||session!==this.loopSession)this.lastLoopFailure=null;
      this.loopSession=session;
      this.loopCycle=b.cycle;
      const sync=b.native?.sync;
      const counts=totals?` · 本次服务读取 ${totals.total_reads} 轮 · 异常 ${totals.failed_reads} 轮${finite(totals.complete_but_late)?` · 收齐但超时 ${totals.complete_but_late} 轮${finite(totals.accepted_complete_but_late)?`（已接纳 ${totals.accepted_complete_but_late} 轮）`:''}`:''}`:' · 当前服务未提供累计计数';
      this.$('status').textContent=`${context||'使用现有运动循环数据'} · 第 ${b.cycle} 轮${finite(sync?.elapsed_us)?` · 本轮 ${(sync.elapsed_us/1000).toFixed(2)} ms`:''}${counts}`;
      this.paintDevices(s,{loop:true,live:live});
    }else if(this.manual&&this.base&&counters&&b.session===this.base.session){
      const rounds=Math.max(0,b.total_cycles-this.base.cycle),failed=Math.max(0,b.total_communication_failures-this.base.failures);
      this.summary=`读取 ${rounds} 轮 · 成功 ${Math.max(0,rounds-failed)} 轮 · 异常 ${failed} 轮`;
      this.$('status').textContent=`${context||'检测中'} · ${this.summary}`;
      this.paintDevices(s,{rounds,live:live});
    }else{
      this.loopCycle=undefined;this.lastLoopFailure=null;
      this.$('status').textContent=context||this.summary&&`已停止 · ${this.summary} · 保留本次结果`||'未启动运动循环，点击“开始检测”测试通信';
      // A loop that just stopped must not leave a row labelled live/normal.
      this.paintDevices(s,{live:live});
    }
    const deviceStats=deviceStatsOf(b);
    if(deviceStats){
      if(!loop)this.$('status').textContent+=` · 本次服务累计采集 ${deviceStats.total_reads} 轮`;
      this.$('status').textContent+=` · 完整回包超时 ${deviceStats.complete_but_late??0} 轮（整轮，未归因到设备）`;
    }
    this.wasLoop=loop;
    this.paintStatus(s,{loop,live,context});
  }
  paintDevices(s,{loop=false,rounds=0,live}){
    const b=s.bus,stats=deviceStatsOf(b),trace=stats?.last_trace||b.native?.sync||b.diagnostics?.sync,totals=loop?totalsOf(b):null;
    // A torque-confirmation Sync Read is not a 16-device telemetry frame.
    const telemetry=trace?.address===56&&trace?.length===15;
    const missing=new Set(telemetry&&trace.request_sent!==false?trace.missing_ids||[]:[]),errors=errorsOf(b);
    for(const [id,{cell,detail}] of this.cells){
      const row=id===200?s.imu:s.servos?.find(r=>r.id===id),fresh=live&&s.service_sample_fresh&&row?.status==='live';
      const device=separatedCounts(stats,id);
      const legacyCount=loop?(totals?totals.missing_by_id[id]||0:null):this.base?Math.max(0,(errors[id]||0)-(this.base.errors[id]||0)):errors[id]??null;
      const failures=device?.missing, timeouts=device?.timeout;
      let label,tone='';
      if(!live){label='反馈暂停 / 中断';tone='warn';}
      else if(telemetry&&missing.has(id)){label=trace.deadline_exceeded?'本轮超时未回':'本轮非超时缺包';tone=trace.deadline_exceeded?'warn':'bad';}
      else if(telemetry&&trace.request_sent===false){label='总线请求发送失败';tone='warn';}
      else if(telemetry&&trace.complete_but_late){label=acceptedLateRead(b)?'回包齐全 · 超时已接纳':'回包齐全 · 本轮超时';tone='warn';}
      else if(loop&&!fresh){label=telemetry&&!missing.has(id)?'本轮有回包 · 样本未更新':'等待新鲜反馈';tone='warn';}
      else if((failures||timeouts||!device&&legacyCount)&&fresh){label='当前正常 · 曾'+(timeouts?'超时未回':failures?'非超时缺包':'未回（旧版未分类）');tone='warn';}
      else if(failures||timeouts){label='等待恢复';tone='warn';}
      else if(fresh&&(loop||rounds||stats?.total_reads)){label='通信正常';tone='good';}
      else{label=rounds?'等待新鲜反馈':'等待第一轮';tone=rounds?'warn':'';}
      const current=id===200?`IMU ${fresh?'在线':'等待有效数据'}`:`${fmt(row?.voltage_v)} V · ${fmt(row?.temperature_c,0)} °C${fresh?'':'（上次有效值）'}`;
      const timeoutMs=finite(device?.last_timeout_elapsed_us)?(device.last_timeout_elapsed_us/1000).toFixed(3)+' ms':'— ms';
      const history=device?`\n累计非超时缺包 ${failures} 次\n累计超时未回 ${finite(timeouts)?timeouts+' 次':'未上报'}${finite(device.consecutive_timeout)?`\n连续：超时 ${device.consecutive_timeout} / 缺包 ${device.consecutive_missing}`:''}${finite(device.last_timeout_read)?`\n最近超时：第 ${device.last_timeout_read} 次采集 · ${timeoutMs}`:''}${finite(device.last_missing_read)?`\n最近缺包：第 ${device.last_missing_read} 次采集`:''}`:`\n旧版未回 / 异常 ${finite(legacyCount)?legacyCount+' 次':'未上报'}\n超时与缺包未分开上报，请升级固件`;
      cell.className='inspection-device '+tone;detail.textContent=label+history+'\n'+current;
    }
  }
  paintStatus(s,{context}){
    const message=this.requestError||context||'',tone=this.requestError?'error':'info';
    const feedback=this.readOrderControl.feedback(message,tone);
    showFeedback(this.$('feedback'),feedback.message,feedback.tone);
  }
}
