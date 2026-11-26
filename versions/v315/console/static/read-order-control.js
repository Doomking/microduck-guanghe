import {controlFetch} from './control-session.js';
const compact=v=>String(v||'').replace(/\s*[\r\n]+\s*/g,' · ').trim();
export class ReadOrderControl {
  constructor(cfg,root,cells,repaint){
    Object.assign(this,{cfg,root,repaint,cells,buttons:new Map(),loaded:false});
    this.line=document.createElement('p');this.line.id='inspection-order';this.line.className='tiny inspection-order';
    root.querySelector('#inspection-feedback').before(this.line);
    for(const [id,{cell}] of cells)if(id!==200){
      const button=document.createElement('button');button.type='button';button.className='button inspection-reorder';button.textContent='换序';
      button.disabled=true;button.onclick=()=>this.move(id);cell.append(button);this.buttons.set(id,button);
    }
  }
  lost(id){
    const stats=this.s?.bus?.device_communication,row=stats?.by_id?.[id];if(!row)return 0;
    return stats.classification==='exclusive-v2'?row.missing+row.timeout:Math.max(row.missing,row.timeout);
  }
  live(){return this.s?.channels?.bus?.status==='live'&&!this.options?.offline&&!this.options?.replay&&!this.s?.service_operation;}
  async api(path,body){
    const reply=await controlFetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Control-Token':this.cfg.control_token},body:JSON.stringify(body),signal:AbortSignal.timeout(4000)});
    const value=await reply.json();if(!reply.ok)throw Error(value.error||'换序未确认');return value;
  }
  render(s,options){
    this.s=s;this.options=options;const key=s.bus?.device_communication?.session;
    if(key!==this.key){this.key=key;this.report=null;this.waiting=null;this.loaded=false;this.message='';}
    const connected=s.channels?.bus?.status==='live'&&!options.offline&&!options.replay;
    if(connected&&!this.wasConnected)this.loaded=false;this.wasConnected=connected;
    const live=this.live();
    const order=this.report?.read_order;
    this.line.textContent=order?.applied?.length?'读取顺序：'+order.applied.join('→')+(order.pending?'（更新中）':''):'读取顺序：等待读回';
    for(const [id,button] of this.buttons){
      const lost=this.lost(id);button.disabled=!this.live()||!(lost>10)||!!this.pending||!!this.waiting||order?.applied?.at(-1)===id;
      button.title=order?.applied?.at(-1)===id?'已在读取末尾':lost<=10?`累计未回包 ${lost} 次，超过 10 次可换序`:'移到读取末尾并保存';
    }
    if(live&&!this.loaded&&!this.pending&&!this.reading&&!document.hidden&&this.root.isConnected&&!this.root.closest('[hidden]'))void this.read();
  }
  async read(){
    if(this.reading)return this.reading;const key=this.key;this.loaded=true;
    this.reading=(async()=>{
    try{
      const value=await this.api('/api/service/read-order/status',{});if(this.key!==key)return;
      this.report=value.report;
      if(this.readError){this.message='';this.readError=false;}
      if(this.waiting&&this.report?.read_order?.applied_revision>=this.waiting.revision&&!this.report.read_order.pending){
        this.message=`ID ${this.waiting.id} · 换序成功，已移至末尾并保存`;this.tone='completed';this.waiting=null;
      }
    }catch(error){if(this.key===key&&!this.report){this.message=error.message.includes('unknown variant `read-order-status`')?'换序接口未就绪，请安装随包 control.127':'读取顺序未回读：'+error.message;this.tone='warning';this.readError=true;}}
    finally{this.reading=null;this.repaint();}
    })();return this.reading;
  }
  async move(id){
    if(!this.live()||!(this.lost(id)>10)||this.pending||this.waiting)return;
    this.pending=true;this.message=`ID ${id} · 换序中`;this.tone='info';this.repaint();
    try{
      if(!this.report)await this.read();
      const order=this.report?.read_order,session=this.report?.device_communication?.session;
      if(!order||!session)throw Error('换序接口未读回，请升级随包固件');
      const value=await this.api('/api/service/read-order',{id,session,revision:order.revision});
      if(value.accepted!==true)throw Error(value.reason||'换序未确认');
      this.waiting={id,revision:value.read_order.revision};this.message=`ID ${id} · 已保存，待生效`;this.tone='warning';
      await new Promise(resolve=>setTimeout(resolve,100));
      await this.read();
    }catch(error){this.message=`ID ${id} · ${error.message}；指令未自动重发`;this.tone='error';}
    finally{this.pending=false;this.waiting=null;this.repaint();}
  }
  feedback(message,tone){
    return {message:compact([this.message,message].filter(Boolean).join(' · ')),tone:this.message?this.tone||tone:tone};
  }
}
