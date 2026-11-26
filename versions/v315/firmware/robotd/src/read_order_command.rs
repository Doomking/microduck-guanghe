//! Validation shared by the IPC handler and its in-process acceptance tests.
use duck_control::feetech_order::{ReadOrder,Report};
use crate::communication_stats::CommunicationStats;

pub fn move_last(order:&ReadOrder,stats:&CommunicationStats,id:u8,session:&str,revision:u64)->Result<Report,String> {
    if stats.session!=session {return Err("通信会话已改变，请等待本次服务回读后重试".into());}
    if !duck_control::model::JOINT_IDS.contains(&id) {return Err("换序仅支持当前 15 个舵机，IMU 200 固定首位".into());}
    let counts=stats.by_id.get(&id).ok_or("尚未取得该舵机的通信统计")?;
    if counts.missing.saturating_add(counts.timeout)<=10 {
        return Err("该舵机累计未回包必须超过 10 次，当前不能换序".into());
    }
    order.move_last(id,revision)
}
