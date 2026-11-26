"""Test actual maintenance code using simulated UART timing and real process pipes.

Usage: python3 performance-check.py /absolute/Microduck-Console-Studio-V301.zip
UART timing below is a model, not a measurement of ZERO or a physical servo.
"""
from pathlib import Path
import io,json,os,struct,subprocess,sys,tempfile,threading,time,types,unittest,zipfile
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
BASELINE=Path(sys.argv.pop(1)) if len(sys.argv)>1 else None
import maintenance_worker as w
import service_rpc as rpc
from manage_stdin import STREAM_WRAPPER_SOURCE,framed_input
from maintenance_control import MaintenanceController
from controls import ControlError
from service_control import ServiceTransport

legacy=None
if BASELINE is not None:
    with zipfile.ZipFile(BASELINE) as z:
        legacy=types.ModuleType('legacy_maintenance_worker');legacy.__file__=str(ROOT/'maintenance_worker.py')
        exec(compile(z.read('Microduck-Console-Studio-V301/maintenance_worker.py'),legacy.__file__,'exec'),legacy.__dict__)
metrics={}
class Clock:
    def __init__(self):self.now=100.;self.sleep_ms=0.
    def __call__(self):return self.now
    def sleep(self,n):self.now+=n;self.sleep_ms+=n*1000
class Bus:
    def __init__(self,module,clock):
        self.w=module;self.clock=clock;self.bad_checksums=0;self.last_probe=None;self.events=[];self.data={};self.drop_id=False;self.drop_center=False;self.delay_center=0.;self.pending=None
        for ident in (1,20,21):self.add(ident)
    def add(self,ident):
        mem=bytearray(80);mem[:8]=bytes((3,50,0,10,0,ident,0,ident));mem[55]=1;mem[56:58]=struct.pack('<H',1000);self.data[ident]=mem
    def event(self,kind,ident,*args):self.events.append((kind,ident,*args));self.clock.now+=.0002
    def ping(self,ident,timeout=.008):
        self.event('ping',ident)
        if ident not in self.data and ident!=200:self.clock.now+=timeout;raise self.w.BusTimeout('no response')
    def scan_ping(self,ident):
        self.last_probe={'id':ident,'valid_replies':0,'unexpected':0,'inconsistent':False};self.ping(ident)
        self.last_probe['valid_replies']=1;self.clock.now+=.002
    def read(self,ident,address,width):
        self.event('read',ident,address,width)
        if ident==200:return self.w.IMU_IDENTITY[:width]
        if ident not in self.data:self.clock.now+=.035;raise self.w.BusTimeout('no response')
        if self.pending and self.clock.now>=self.pending[0]:
            self.data[self.pending[1]][56:58]=struct.pack('<H',2048);self.data[self.pending[1]][31:33]=struct.pack('<H',100);self.pending=None
        return bytes(self.data[ident][address:address+width])
    def scan_read(self,ident,address,width):
        self.last_probe={'id':ident,'valid_replies':1,'unexpected':0,'inconsistent':False}
        result=self.read(ident,address,width);self.clock.now+=.002;return result
    def write(self,ident,address,value,accepted_ids=None):
        self.event('write',ident,address,value)
        if address==5:
            assert self.data[ident][55]==0 and self.data[ident][40]==0
            mem=self.data.pop(ident);mem[5]=value;self.data[value]=mem
            if self.drop_id:self.drop_id=False;raise self.w.BusTimeout('lost ID ACK')
        else:self.data[ident][address]=value
    def _numbering_secondary(self,ident):self.event('secondary',ident);self.data[ident][7]=ident
    def _swap_id(self,ident,value,old,new,temporary):self.write(ident,5,value,accepted_ids=(ident,value))
    def calibrate_center(self,ident):
        self.event('center',ident);assert self.data[ident][55]==0 and self.data[ident][40]==0
        if self.delay_center:self.pending=(self.clock.now+self.delay_center,ident)
        else:self.data[ident][56:58]=struct.pack('<H',2048);self.data[ident][31:33]=struct.pack('<H',100)
        if self.drop_center:self.drop_center=False;raise self.w.BusTimeout('lost recal ACK')
class Probe:
    def __init__(self):self.reads=0;self.value=False
    def state(self):return self.value
    def fresh(self):self.reads+=1;return self.value
    def close(self):pass
def fixture(module=w):
    clock=Clock();bus=Bus(module,clock)
    s=module.Session({'mode':'numbering','token':'a'*64},bus,service_check=lambda:{'robotd_running':False},clock=clock,calibration_invalidator=lambda ident:{'invalidated':ident})
    rows=[]
    for ident in (1,20,21):
        rows.append({**s._identity(ident,bytes(bus.data[ident][:8])),'identity_verified':True,'torque_on':False,'position_raw':1000})
    rows.append(s._identity(200,module.IMU_IDENTITY));s.servo_rows=rows;s.service_probe=Probe()
    s.scan_progress.update(state='completed',completed=True,running=False,requires_rescan=False,generation=1,scanned=250,total=250,found=4,conflict_ids=[],error='')
    return s,bus,clock
def request(action,**params):return {'action':action,'token':'a'*64,**params}
def change(old=1,new=10):return request('write',old_id=old,new_id=new,selected_servo_confirmed=True)
def center():return request('center-calibrate',servo_id=1,selected_servo_confirmed=True,center_confirmed=True)
class Tests(unittest.TestCase):
    def test_ordinary_write_reuses_scan_and_only_addresses_participants(self):
        s,b,c=fixture();result=s.handle(change());self.assertTrue(result['receipt']['verified'])
        self.assertEqual({e[1] for e in b.events},{1,10});self.assertEqual(sum(e[0]=='write' and e[2]==5 for e in b.events),1)
        self.assertEqual(s.service_probe.reads,0);self.assertFalse(s.scan_progress['requires_rescan'])
        s.handle(change(20,11));self.assertEqual(s.scan_progress['generation'],1)
        self.assertTrue(s.receipt['verified']);self.assertEqual({r['id'] for r in s.servo_rows},{10,11,21,200})
    def test_scan_is_required_and_cannot_silently_fall_back_to_full_scan(self):
        s,b,c=fixture();s.scan_progress['requires_rescan']=True
        with self.assertRaises(w.MaintenanceError):s.handle(change())
        self.assertEqual(b.events,[])
    def test_invalid_owner_does_not_touch_uart(self):
        s,b,c=fixture()
        with self.assertRaises(w.MaintenanceError):s.handle({**change(),'token':'b'*64})
        self.assertEqual(b.events,[])
    def test_occupied_target_and_cached_secondary_alias_refuse_before_id_write(self):
        for alias in (False,True):
            s,b,c=fixture()
            if alias:s.servo_rows[1]['secondary_id']=10
            else:b.add(10)
            with self.assertRaises(w.MaintenanceError):s.handle(change())
            self.assertFalse(any(e[0]=='write' and e[2]==5 for e in b.events))
    def test_changed_selected_identity_and_bad_feedback_refuse(self):
        for kind in ('identity','feedback','duplicate'):
            s,b,c=fixture()
            if kind=='identity':b.data[1][1]=51
            elif kind=='feedback':s.position_failed.add(20)
            else:s.servo_rows[0]['suspected_duplicate']=True
            with self.assertRaises(w.MaintenanceError):s.handle(change())
            self.assertFalse(any(e[0]=='write' for e in b.events))
    def test_lost_id_ack_is_read_back_once_without_replaying(self):
        s,b,c=fixture();b.drop_id=True;result=s.handle(change())
        self.assertTrue(result['receipt']['verified']);self.assertEqual(sum(e[0]=='write' and e[2]==5 for e in b.events),1)
    def test_center_is_single_shot_and_waits_only_when_feedback_is_not_ready(self):
        for delayed,lost in ((0,False),(.025,False),(0,True)):
            s,b,c=fixture();b.delay_center=delayed;b.drop_center=lost
            with patch.object(w.time,'sleep',c.sleep):result=s.handle(center())
            receipt=result['center_receipt'];self.assertTrue(receipt['verified']);self.assertTrue(receipt['relocked']);self.assertTrue(receipt['torque_off'])
            self.assertEqual(receipt['command_count'],1);self.assertEqual(sum(e[0]=='center' for e in b.events),1)
            self.assertEqual(s.service_probe.reads,0)
            if not delayed:self.assertEqual(c.sleep_ms,0)
            else:self.assertGreater(c.sleep_ms,0)
            self.assertFalse(any(e[0]=='write' and e[2] not in (40,55) for e in b.events))
    def test_center_protection_failure_sends_no_recal_and_relocks(self):
        s,b,c=fixture();s.calibration_invalidator=lambda ident:(_ for _ in ()).throw(OSError('disk unavailable'))
        with self.assertRaises(w.MaintenanceError):s.handle(center())
        self.assertEqual(sum(e[0]=='center' for e in b.events),0);self.assertEqual(b.data[1][55],1)
    def test_swap_uses_three_single_shot_id_writes_and_three_addresses(self):
        s,b,c=fixture();b.data[21][1]=51;s.servo_rows[2]['firmware'][1]=51;b.drop_id=True
        result=s.handle(request('write',old_id=20,new_id=21,swap=True,selected_servo_confirmed=True))
        self.assertTrue(result['receipt']['verified']);self.assertEqual({e[1] for e in b.events},{20,21,250})
        self.assertEqual(sum(e[0]=='write' and e[2]==5 for e in b.events),3)
        self.assertEqual((b.data[20][1],b.data[21][1]),(51,50))
    def test_center_missing_settling_feedback_remains_uncertain_without_replay(self):
        s,b,c=fixture();b.delay_center=.2
        with patch.object(w.time,'sleep',c.sleep),self.assertRaises(w.MaintenanceError):s.handle(center())
        self.assertEqual(sum(e[0]=='center' for e in b.events),1);self.assertTrue(s.center_receipt['uncertain']);self.assertEqual(b.data[1][55],1)
    def test_unknown_service_state_cannot_write(self):
        s,b,c=fixture();s.service_probe.value=None
        with self.assertRaises(w.MaintenanceError):s.handle(change())
        self.assertTrue(s.ended);self.assertEqual(b.events,[])
    def test_expired_lease_and_stale_service_observation_cannot_write(self):
        s,b,c=fixture();c.now+=w.LEASE_SECONDS+1;s.tick()
        with self.assertRaises(w.MaintenanceError):s.handle(change())
        self.assertEqual(b.events,[])
        probe=w.ServiceProbe.__new__(w.ServiceProbe);probe.lock=threading.Lock();probe.value=False;probe.at=100
        with patch.object(w.time,'monotonic',return_value=100.8):self.assertIsNone(probe.state())
    def test_execute_sends_one_daemon_request_per_hot_operation(self):
        for action in ('status','write','center-calibrate','end'):
            with patch.object(w,'send_request',return_value={'active':True,'owned':True}) as send:
                w.execute(request(action));self.assertEqual(send.call_count,1)
    def test_controller_hot_calls_do_not_spawn_compatibility_probes(self):
        s,b,c=fixture()
        class Transport:
            target='fixture-zero';path='/run/robotd.sock'
            def __init__(self):self.probes=0;self.calls=0
            def _manage(self,*a,**kw):self.probes+=1;return {'maintenance_installed':True,'maintenance_stream':True}
            def maintenance_call(self,path,payload,password=None):
                self.calls+=1;return {**s.handle(payload),'_position_barrier_ns':time.monotonic_ns()}
        class Positions:
            def invalidate(self):pass
            def begin_revision(self):pass
            def begin_selected(self,*a):pass
            def observe(self,*a):pass
            def metadata(self):return {}
        t=Transport();core=MaintenanceController(transport_provider=lambda:t)
        try:
            core._observe_transport(t);core.positions=Positions();core.token='a'*64;core.session_target=core._target(t);core.cache=s.snapshot(True)
            for old,new in [(1,10),(20,11)]:
                payload=change(old,new);payload.pop('token');core.handle(payload)
            self.assertEqual(t.probes,1);self.assertEqual(t.calls,2)
            t=Transport()
            with self.assertRaises(ControlError):core.handle({k:v for k,v in change(21,12).items() if k!='token'})
            self.assertEqual(t.calls,0,'a new transport must not inherit the preceding owner token')
        finally:core.closed=True;core.stop_event.set();core.heartbeat.join(1)
    @unittest.skipIf(legacy is None, 'Optional V301 comparison archive not supplied; no timing claim')
    def test_simulated_before_after_operation_budget(self):
        for label,operation in [('write',change()),('center',center())]:
            rows={}
            for name,module in [('V301',legacy),('V302',w)]:
                s,b,c=fixture(module);start=c()
                with patch.object(module.time,'sleep',c.sleep):s.handle(operation)
                rows[name]={'simulated_uart_and_fixed_wait_ms':round((c()-start)*1000,3),'address_count':len({e[1] for e in b.events}),
                    'packet_count':len(b.events),'service_query_count':s.service_probe.reads,'fixed_sleep_ms':round(c.sleep_ms,3)}
            metrics[label]=rows
            self.assertLess(rows['V302']['simulated_uart_and_fixed_wait_ms'],rows['V301']['simulated_uart_and_fixed_wait_ms'])
        self.assertEqual(metrics['write']['V301']['address_count'],254);self.assertEqual(metrics['write']['V302']['address_count'],2)
    def test_real_pipe_helper_reuses_pid_and_authenticates_only_at_start(self):
        code="import json,os,sys\nprint(json.dumps({'maintenance_client_ready':1}),flush=True)\nfor raw in sys.stdin:\n f=json.loads(raw);print(json.dumps({'id':f['id'],'result':{'pid':os.getpid(),'echo':f['request']['action']}}),flush=True)\n"
        for consumed in (False,True):
            pool=rpc.PersistentMaintenance();argv=[sys.executable,'-u','-c',STREAM_WRAPPER_SOURCE,sys.executable,'-u','-c',code]
            startup=framed_input('', 'fixture-auth-only');startup=startup.split('\n',1)[1] if consumed else startup
            try:
                with patch.object(rpc.subprocess,'Popen',wraps=subprocess.Popen) as spawn:
                    pids=[]
                    for action in ('status','write','center-calibrate','status'):
                        reply=pool.call({'argv':argv,'input':startup,'request':{'action':action}})
                        self.assertEqual(reply['returncode'],0,reply);pids.append(json.loads(reply['stdout'])['pid'])
                    self.assertEqual(spawn.call_count,1);self.assertEqual(len(set(pids)),1)
            finally:pool.close()
    def test_pipe_failure_after_send_never_replays_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker=Path(tmp)/'count';code="import json,sys\nfrom pathlib import Path\nprint(json.dumps({'maintenance_client_ready':1}),flush=True)\nf=json.loads(sys.stdin.readline());Path(sys.argv[1]).write_text('once');sys.exit(7)\n"
            pool=rpc.PersistentMaintenance()
            try:
                with patch.object(rpc.subprocess,'Popen',wraps=subprocess.Popen) as spawn:
                    reply=pool.call({'argv':[sys.executable,'-u','-c',code,str(marker)],'request':{'action':'write'},'input':''})
                    self.assertEqual(reply['returncode'],1);self.assertEqual(spawn.call_count,1);self.assertEqual(marker.read_text(),'once')
            finally:pool.close()
    def test_bad_stream_auth_frame_never_executes_client(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker=Path(tmp)/'client-started';code="from pathlib import Path;import sys;Path(sys.argv[1]).write_text('started')"
            pool=rpc.PersistentMaintenance()
            try:
                reply=pool.call({'argv':[sys.executable,'-u','-c',STREAM_WRAPPER_SOURCE,sys.executable,'-u','-c',code,str(marker)],
                    'input':'fixture-password\nBAD-FRAME\n','request':{'action':'write'}})
                self.assertEqual(reply['returncode'],1);self.assertFalse(marker.exists());self.assertNotIn('fixture-password',reply['stderr'])
            finally:pool.close()
    def test_production_transport_uses_empty_startup_auth_and_separate_command(self):
        t=ServiceTransport(None,'/run/robotd.sock');captured=[]
        def channel(payload,**kw):captured.append(payload);return {'returncode':0,'stdout':'{"active":true}','stderr':''}
        t.channel.request=channel
        try:
            t.maintenance_call('/opt/robot/feetech-ft5-r5/maintenance_worker.py',change(),password='fixture-auth')
            payload=captured[0];self.assertEqual(payload['kind'],'maintenance');self.assertEqual(payload['request'],change())
            self.assertIn(STREAM_WRAPPER_SOURCE,payload['argv']);self.assertEqual(payload['input'],framed_input('','fixture-auth'))
        finally:t.channel.close()
    def test_production_worker_stream_keeps_position_barrier_and_refusal_state(self):
        def execute(payload):
            if payload['action']=='center-calibrate':raise w.MaintenanceError('precheck refused',409)
            return {'active':True,'owned':True,'action':payload['action']}
        frames=b''.join((json.dumps({'id':i,'request':payload})+'\n').encode() for i,payload in enumerate([change(),center()],1));out=io.StringIO()
        with patch.object(w,'execute',side_effect=execute) as call,patch.object(w.sys,'stdin',types.SimpleNamespace(buffer=io.BytesIO(frames))),patch.object(w.sys,'stdout',out):w.client_stream()
        lines=[json.loads(row) for row in out.getvalue().splitlines()]
        self.assertEqual(lines[0],{'maintenance_client_ready':1});self.assertEqual([x['id'] for x in lines[1:]],[1,2])
        self.assertTrue(all(x['result']['_position_barrier_ns']>0 for x in lines[1:]));self.assertIn('_position_failure_state',lines[2]['result'])
        self.assertEqual([a.args[0]['action'] for a in call.call_args_list],['write','center-calibrate','status'])

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Tests);result=unittest.TextTestRunner(verbosity=2).run(suite)
    report={'passed':result.wasSuccessful(),'tests':result.testsRun,'passed_tests':result.testsRun-len(result.skipped)-len(result.failures)-len(result.errors),'skipped':len(result.skipped),'simulated_before_after':metrics,
        'timing_model':'8 ms per silent address; 0.2 ms per UART operation; 2 ms duplicate-reply collection; actual fixed sleeps. SSH, service process costs and calibration disk persistence excluded.',
        'real_pipe_subprocesses_tested':True,'real_ssh_or_uart_tested':False,'physical_latency_ms':None,'one_ms_claim':False}
    Path(__file__).with_name('performance-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
