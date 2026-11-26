//! Persistent ordering of telemetry requests. Joint arrays, packet decoding,
//! writes and transaction deadlines do not depend on this order.
use serde::{Deserialize,Serialize};
use std::io::{Read,Write};
use std::path::{Path,PathBuf};
use std::sync::{Arc, Mutex};

#[derive(Clone, Default)]
pub struct ReadOrder(Arc<Inner>);

#[derive(Default)]
struct Inner {
    state: Mutex<State>,
    change: Mutex<()>,
    path: Option<PathBuf>,
}

#[derive(Serialize,Deserialize)]
#[serde(deny_unknown_fields)]
struct Saved {
    schema: String,
    revision: u64,
    ids: Vec<u8>,
}

#[derive(Default)]
struct State {
    desired: Vec<u8>,
    applied: Vec<u8>,
    revision: u64,
    applied_revision: Option<u64>,
    saved_revision: Option<u64>,
    storage_error: Option<String>,
}

pub struct Plan {
    pub ids: Vec<u8>,
    revision: u64,
}

#[derive(Clone, Serialize)]
pub struct Report {
    pub schema: &'static str,
    pub revision: u64,
    pub applied_revision: Option<u64>,
    pub desired: Vec<u8>,
    pub applied: Vec<u8>,
    pub pending: bool,
    pub baud: u32,
    pub deadline_us: u64,
    pub address: u8,
    pub length: u8,
    pub instruction: u8,
    pub persistence: &'static str,
    pub saved_revision: Option<u64>,
    pub storage_error: Option<String>,
}

impl ReadOrder {
    /// The params directory is already writable by robotd and retained by the
    /// installer. No saved order is bundled or created during ordinary startup.
    pub fn persistent(path:PathBuf)->Self {
        let mut state=State::default();
        let load=(||->Result<Option<Saved>,String>{
            let file=match std::fs::File::open(&path){
                Ok(file)=>file,
                Err(e) if e.kind()==std::io::ErrorKind::NotFound=>return Ok(None),
                Err(e)=>return Err(e.to_string()),
            };
            let mut raw=Vec::new();file.take(4097).read_to_end(&mut raw).map_err(|e|e.to_string())?;
            if raw.len()>4096{return Err("保存记录过长".into());}
            let saved:Saved=serde_json::from_slice(&raw).map_err(|e|e.to_string())?;
            let mut ids=saved.ids.clone();ids.sort_unstable();
            let mut expected=crate::model::JOINT_IDS.to_vec();expected.push(crate::feetech::IMU_ID);expected.sort_unstable();
            if saved.schema!="feetech-read-order/v1" || saved.revision>9_007_199_254_740_991
                || saved.ids.first()!=Some(&crate::feetech::IMU_ID) || ids!=expected {
                return Err("保存的读取顺序格式或设备列表无效".into());
            }
            Ok(Some(saved))
        })();
        match load {
            Ok(Some(saved))=>{state.desired=saved.ids;state.revision=saved.revision;state.saved_revision=Some(saved.revision);}
            Ok(None)=>{},
            Err(error)=>{
                let reason=format!("读取保存顺序失败，保留原记录并暂用默认顺序：{error}");
                tracing::warn!(%reason);state.storage_error=Some(reason);
            }
        }
        Self(Arc::new(Inner{state:Mutex::new(state),change:Mutex::new(()),path:Some(path)}))
    }

    pub fn plan(&self, servo_ids: &[u8]) -> Result<Plan, String> {
        let mut state=self.0.state.lock().map_err(|_| "读取顺序状态不可用")?;
        let mut ids=vec![crate::feetech::IMU_ID];
        ids.extend_from_slice(servo_ids);
        if state.desired.is_empty() {state.desired=ids.clone();}
        let mut expected=ids;expected.sort_unstable();
        let mut configured=state.desired.clone();configured.sort_unstable();
        if configured!=expected {return Err("读取设备已改变，请重新启动服务后核对".into());}
        Ok(Plan {ids:state.desired.clone(),revision:state.revision})
    }

    /// Called only after the complete request was sent, even if replies failed.
    pub fn sent(&self, plan: &Plan) {
        if let Ok(mut state)=self.0.state.lock() {
            state.applied=plan.ids.clone();state.applied_revision=Some(plan.revision);
        }
    }

    pub fn move_last(&self,id:u8,revision:u64)->Result<Report,String> {
        let _change=self.0.change.lock().map_err(|_| "读取顺序保存不可用")?;
        let mut desired={
            let state=self.0.state.lock().map_err(|_| "读取顺序状态不可用")?;
            if id==crate::feetech::IMU_ID {return Err("IMU 200 固定首位，不能换序".into());}
            if revision!=state.revision {return Err("读取顺序已更新，请等待当前顺序回读后重试".into());}
            if state.applied_revision!=Some(state.revision) {return Err("上一条读取顺序尚未发出，请等待回读".into());}
            let at=state.desired.iter().position(|v|*v==id).ok_or("该舵机不在当前读取队列中")?;
            if at+1==state.desired.len() {return Err("该舵机已经在读取末尾".into());}
            let mut ids=state.desired.clone();ids.remove(at);ids.push(id);ids
        };
        let next=revision.checked_add(1).filter(|v|*v<=9_007_199_254_740_991).ok_or("读取顺序版本达到上限")?;
        // Only the IPC writer takes `change`. Never hold the telemetry state
        // lock during filesystem I/O: the control loop continues using its old plan.
        if let Some(path)=&self.0.path {
            if let Err(error)=save(path,&Saved{schema:"feetech-read-order/v1".into(),revision:next,ids:desired.clone()}) {
                let reason=format!("换序保存未确认，请核对当前实际顺序：{error}");
                if let Ok(mut state)=self.0.state.lock(){state.storage_error=Some(reason.clone());}
                return Err(reason);
            }
        }
        let mut state=self.0.state.lock().map_err(|_| "读取顺序状态不可用")?;
        state.desired=std::mem::take(&mut desired);state.revision=next;
        state.saved_revision=self.0.path.as_ref().map(|_|next);state.storage_error=None;
        Ok(Self::describe(&state,self.0.path.is_some()))
    }

    pub fn report(&self)->Report {
        Self::describe(&self.0.state.lock().expect("read order lock poisoned"),self.0.path.is_some())
    }

    fn describe(state:&State,persistent:bool)->Report {
        Report {schema:"feetech-read-order/v1",revision:state.revision,
            applied_revision:state.applied_revision,desired:state.desired.clone(),applied:state.applied.clone(),
            pending:state.applied_revision!=Some(state.revision),baud:crate::feetech::BAUD,
            deadline_us:crate::feetech::TELEMETRY_DEADLINE_MS*1000,
            address:crate::feetech::SYNC_ADDRESS,length:crate::feetech::SYNC_LENGTH,
            instruction:0x82,persistence:if persistent {"robot_config"}else{"process_session"},
            saved_revision:state.saved_revision,storage_error:state.storage_error.clone()}
    }
}

fn save(path:&Path,saved:&Saved)->Result<(),String> {
    let raw=serde_json::to_vec(saved).map_err(|e|e.to_string())?;
    let parent=path.parent().filter(|p|!p.as_os_str().is_empty()).unwrap_or_else(||Path::new("."));
    let directory=std::fs::File::open(parent).map_err(|e|e.to_string())?;
    let stamp=std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap_or_default().as_nanos();
    let temp=path.with_file_name(format!(".telemetry-read-order-{}-{stamp}.tmp",std::process::id()));
    let result=(||->std::io::Result<()>{
        let mut options=std::fs::OpenOptions::new();options.write(true).create_new(true);
        #[cfg(unix)] {use std::os::unix::fs::OpenOptionsExt;options.mode(0o644);}
        let mut file=options.open(&temp)?;file.write_all(&raw)?;file.sync_all()?;
        std::fs::rename(&temp,path)?;directory.sync_all()
    })();
    if result.is_err(){let _=std::fs::remove_file(&temp);}
    result.map_err(|e|e.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn stable_move_preserves_imu_and_other_devices_and_waits_for_send() {
        let order=ReadOrder::default();let ids=crate::model::JOINT_IDS;
        let original=order.plan(&ids).unwrap();order.sent(&original);
        let result=order.move_last(12,0).unwrap();
        assert!(result.pending);assert_eq!(result.applied,original.ids);
        assert_eq!(result.desired.first(),Some(&200));assert_eq!(result.desired.last(),Some(&12));
        assert_eq!(result.desired.iter().filter(|v|**v!=12).copied().collect::<Vec<_>>(),
            original.ids.iter().filter(|v|**v!=12).copied().collect::<Vec<_>>());
        assert!(order.move_last(13,0).is_err());assert!(order.move_last(13,1).is_err());
        let next=order.plan(&ids).unwrap();order.sent(&next);
        assert!(!order.report().pending);assert_eq!(order.report().applied,result.desired);
        assert!(order.move_last(12,1).is_err());assert!(order.move_last(200,1).is_err());
        assert!(order.move_last(99,1).is_err());
    }
}
