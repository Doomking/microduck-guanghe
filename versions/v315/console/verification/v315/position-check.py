"""Targeted position-range and per-device failure regressions; no robot required."""
from pathlib import Path
import contextlib,importlib.util,io,json,os,pty,select,struct,sys,threading,time,tty,types,unittest,zipfile
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.dont_write_bytecode=True
import maintenance_worker as w
import maintenance_positions as positions
spec=importlib.util.spec_from_file_location('v302_fixture',ROOT/'verification/v302/performance-check.py')
fixture_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture_module)
fixture=fixture_module.fixture

class Tests(unittest.TestCase):
    def test_read_complete_register_without_single_turn_rejection(self):
        s,b,c=fixture();row=s.servo_rows[0]
        for value in (0,4095,4096,8191,32767,32768,36864,65535):
            with self.subTest(value=value):
                b.data[1][56:58]=struct.pack('<H',value);s.position_failed.add(1)
                s._read_position(row)
                self.assertEqual(row['position_raw'],value);self.assertNotIn('position_error',row)
                self.assertNotIn(1,s.position_failed)

    def test_other_position_failure_does_not_block_numbering(self):
        s,b,c=fixture();s.position_failed.add(20)
        next(r for r in s.servo_rows if r['id']==20).update(position_raw=None,position_error='读取失败')
        s.handle(fixture_module.change(1,10))
        self.assertTrue(s.receipt['verified']);self.assertFalse(s.scan_progress['requires_rescan'])
        self.assertEqual({e[1] for e in b.events},{1,10})
        self.assertEqual(sum(e[0]=='write' and e[2]==5 for e in b.events),1)

    def test_selected_center_accepts_extended_position_and_offset(self):
        s,b,c=fixture();s.position_failed.add(20)
        b.data[1][56:58]=struct.pack('<H',65535);b.data[1][31:33]=struct.pack('<H',9000)
        answer=s.handle(fixture_module.center())
        self.assertTrue(answer['center_receipt']['verified'])
        self.assertEqual(answer['center_receipt']['before_position_raw'],65535)
        self.assertEqual(answer['center_receipt']['after_position_raw'],2048)
        self.assertEqual(sum(e[0]=='center' for e in b.events),1)
        self.assertFalse(s.scan_progress['requires_rescan'])

    def test_actual_uart_partial_frame_isolated_and_recovers_next_cycle(self):
        master,slave=pty.openpty();tty.setraw(slave)
        real=w.SerialBus.__new__(w.SerialBus);real.fd=slave;real.clock=time.monotonic;real.bad_checksums=0
        stop=threading.Event();drop={20};frames=[];errors=[]
        values={1:4096,20:5000,21:65535}
        def respond():
            pending=bytearray()
            try:
                while not stop.is_set():
                    if not select.select([master],[],[],.05)[0]:continue
                    pending.extend(os.read(master,1024))
                    while len(pending)>=4 and len(pending)>=pending[3]+4:
                        size=pending[3]+4;packet=bytes(pending[:size]);del pending[:size]
                        if packet[4]!=0x82:raise AssertionError('Unexpected UART request')
                        ids=list(packet[7:-1]);frames.append(ids)
                        for ident in ids:
                            if ident not in drop:os.write(master,w.packet(ident,0,struct.pack('<H',values[ident])))
            except Exception as e:
                if not stop.is_set():errors.append(e)
        worker=threading.Thread(target=respond,daemon=True);worker.start()
        try:
            s,b,c=fixture();s.bus=real;s.clock=time.monotonic;s.position_due=0
            s._sample_position(time.monotonic());rows={r['id']:r for r in s.servo_rows}
            self.assertEqual(rows[1]['position_raw'],4096);self.assertEqual(rows[21]['position_raw'],65535)
            self.assertNotIn('position_error',rows[1]);self.assertNotIn('position_error',rows[21])
            self.assertEqual(rows[20]['position_error'],'读取失败');self.assertEqual(s.position_failed,{20})
            drop.clear();s.position_due=0;s._sample_position(time.monotonic())
            self.assertEqual(rows[20]['position_raw'],5000);self.assertNotIn('position_error',rows[20])
            self.assertEqual(s.position_failed,set());self.assertEqual(frames,[[1,20,21],[1,20,21]])
            self.assertFalse(errors)
        finally:
            stop.set();worker.join(.2);os.close(master);os.close(slave)

    def test_pc_bridge_preserves_full_register_values(self):
        rows=[{'id':i,'kind':'servo','identity_verified':True,'register_id':i,'position_raw':raw}
              for i,raw in ((1,4096),(20,65535),(21,36864))]
        state={'active':True,'mode':'numbering','session_id':'s','scan':{'completed':True,'running':False,'requires_rescan':False,'generation':1},'devices':rows}
        clock={'now':0.}
        class Socket:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def settimeout(self,v):pass
            def connect(self,v):pass
            def sendall(self,v):self.request=v
            def makefile(self,*args):return io.BytesIO(json.dumps(state).encode()+b'\n')
        sock=types.SimpleNamespace(socket=lambda *a:Socket(),AF_UNIX=1,SOCK_STREAM=1)
        tm=types.SimpleNamespace(monotonic=lambda:clock['now'],monotonic_ns=lambda:1_000_000,
                                sleep=lambda _:clock.update(now=111.))
        output=io.StringIO()
        with patch.dict(sys.modules,{'socket':sock,'time':tm}),patch.object(sys,'stdin',io.StringIO('{"session_id":"s"}\n')),contextlib.redirect_stdout(output):
            exec(compile(positions.POSITION_BRIDGE_SOURCE,'position-bridge','exec'),{})
        frame=json.loads(output.getvalue().splitlines()[0])
        self.assertEqual([r['position_raw'] for r in frame['positions']],[4096,65535,36864])
        self.assertTrue(all('position_error' not in r for r in frame['positions']))

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    report={'passed':result.wasSuccessful(),'tests':result.testsRun,'full_register_positions':True,
        'per_device_failure_isolation':True,'automatic_recovery_without_rescan':True,
        'single_selected_center_command':True,'actual_pty_packets':True,'physical_hardware_tested':False}
    Path(__file__).with_name('position-results.json').write_text(json.dumps(report,indent=2)+'\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
