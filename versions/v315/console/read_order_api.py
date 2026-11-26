"""Isolated telemetry-order action. No maintenance or motor-register writes."""
from controls import ControlError
from telemetry import IDS

def request(payload,snapshot):
    if not isinstance(payload,dict) or set(payload)!={'id','session','revision'}:
        raise ControlError('换序请求格式无效',400)
    ident=payload['id']
    if type(ident) is not int or ident not in IDS:raise ControlError('请选择舵机；IMU 固定首位',400)
    if not isinstance(payload['session'],str) or type(payload['revision']) is not int:
        raise ControlError('等待读取顺序回读',409)
    bus=snapshot.get('bus') or {};stats=bus.get('device_communication') or {}
    if snapshot.get('channels',{}).get('bus',{}).get('status')!='live' or bus.get('mode') not in ('motion','commissioning'):
        raise ControlError('等待标定或运动服务反馈',409)
    counts=stats.get('by_id',{}).get(str(ident),{})
    lost=(counts.get('missing',0)+counts.get('timeout',0) if stats.get('classification')=='exclusive-v2'
          else max(counts.get('missing',0),counts.get('timeout',0)))
    if lost<=10:raise ControlError('累计未回包超过 10 次后可换序',409)
    return {'action':'read-order-last',**payload}
