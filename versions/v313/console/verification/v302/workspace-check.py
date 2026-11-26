"""Exercise preflight reuse through the actual workspace controller, no hardware."""
from pathlib import Path
import copy,json,sys,threading,time,unittest
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from controls import ControlError
from workspace_control import WorkspaceController

class Components:
    def __init__(self):self.reads=0;self.stops=0;self.running=False;self.needs=False;self.prepares=0;self.core=None;self.worker='/opt/robot/feetech-ft5-r5/maintenance_worker.py'
    def inspect(self,**kw):
        self.reads+=1
        return {'available':True,'active':self.core.current.get('active',False),'owned':self.core.current.get('owned',False),
            'mode':self.core.current.get('mode','idle'),'robotd_running':self.running,'serial_state':'busy' if self.running else 'free',
            'serial_available':not self.running,'requires_component_install':self.needs,'component_id':'f'*64,'worker_path':self.worker}
    def stop(self,**kw):self.running=False;self.stops+=1;return {'robotd_running':False}
    def prepare(self,**kw):
        self.needs=False;self.prepares+=1;self.worker='/opt/robot/feetech-ft5-r5/maintenance-components/'+('f'*64)+'/maintenance_worker.py'
        return {'worker_path':self.worker}
class Core:
    def __init__(self):self.token=None;self.calls=[];self.current={'available':True,'active':False,'owned':False}
    def use_worker(self,*a,**kw):pass
    def status(self,**kw):return self.current
    def handle(self,payload):
        self.calls.append(payload['action'])
        if payload['action']=='begin':self.current={'available':True,'active':True,'owned':True,'mode':payload['mode'],'session_id':'fixture-session','robotd_running':False};self.token='a'*64
        elif payload['action']=='end':self.current={'available':True,'active':False,'owned':False};self.token=None
        return self.current
def fixture():
    store=SimpleNamespace(peek=lambda:{'mode':'service','servos':[]},service_operation=False)
    service=SimpleNamespace(lock=threading.RLock(),transport=SimpleNamespace(target='zero-fixture',path='/run/robotd.sock'),busy=False,stopping=False)
    parts=Components();core=Core();parts.core=core;workspace=WorkspaceController(store,service,core=core,components=parts)
    return workspace,parts,core
def enter(preflight):return {'action':'enter','mode':'numbering','entry_target':preflight['entry_target'],'preflight_id':preflight['preflight_id'],'stop_confirmed':preflight['requires_stop']}
class Tests(unittest.TestCase):
    def test_immediate_stopped_entry_uses_one_component_preflight(self):
        ws,parts,core=fixture();pre=ws.handle({'action':'preflight','mode':'numbering'});answer=ws.handle(enter(pre))
        self.assertTrue(answer['accepted']);self.assertEqual(parts.reads,1);self.assertEqual(core.calls,['begin']);self.assertEqual(parts.stops,0)
    def test_expired_ticket_rechecks_once_but_does_not_repeat_unchanged_inspection(self):
        ws,parts,core=fixture();pre=ws.handle({'action':'preflight','mode':'numbering'});ws.entry_preflight['at']-=3
        ws.handle(enter(pre));self.assertEqual(parts.reads,2);self.assertEqual(core.calls,['begin'])
    def test_ticket_cannot_cross_ssh_transport_or_target(self):
        ws,parts,core=fixture();pre=ws.handle({'action':'preflight','mode':'numbering'})
        ws.service.transport=SimpleNamespace(target='zero-fixture',path='/run/robotd.sock')
        ws.handle(enter(pre));self.assertEqual(parts.reads,2)
        ws,parts,core=fixture();pre=ws.handle({'action':'preflight','mode':'numbering'});ws.service.transport.target='another-zero'
        with self.assertRaises(ControlError):ws.handle(enter(pre))
        self.assertEqual(core.calls,[])
    def test_stop_confirmation_requires_new_service_state_and_serial_inspection(self):
        ws,parts,core=fixture();parts.running=True;pre=ws.handle({'action':'preflight','mode':'numbering'})
        ws.handle(enter(pre));self.assertEqual(parts.reads,3);self.assertEqual(parts.stops,1);self.assertEqual(core.calls,['begin'])
    def test_no_confirmation_does_not_stop_service(self):
        ws,parts,core=fixture();parts.running=True;pre=ws.handle({'action':'preflight','mode':'numbering'})
        with self.assertRaises(ControlError):ws.handle({**enter(pre),'stop_confirmed':False})
        self.assertEqual(parts.stops,0);self.assertEqual(core.calls,[])
    def test_stale_ownership_and_service_busy_do_not_enter(self):
        ws,parts,core=fixture();pre=ws.handle({'action':'preflight','mode':'numbering'});ws.service.busy=True
        with self.assertRaises(ControlError):ws.handle(enter(pre))
        self.assertEqual(core.calls,[])
    def test_owned_old_component_is_replaced_before_reusing_same_page(self):
        ws,parts,core=fixture();parts.needs=True;core.token='a'*64;core.current={'available':True,'active':True,'owned':True,'mode':'numbering'}
        pre=ws.handle({'action':'preflight','mode':'numbering'});ws.handle(enter(pre))
        self.assertEqual(core.calls,['end','begin']);self.assertEqual(parts.prepares,1);self.assertEqual(parts.stops,0)
if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    Path(__file__).with_name('workspace-results.json').write_text(json.dumps({'passed':result.wasSuccessful(),'tests':result.testsRun,'physical_hardware_tested':False},indent=2)+'\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
