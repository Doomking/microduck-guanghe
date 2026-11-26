"""Real robotd, PTY Feetech responder, raw stream and console ServiceController.

No robot, policy or physical UART is used. The responder drops IDs 10/12 for
14 actual telemetry transactions, then replies normally. All RPC bytes travel
through the production Unix-socket handler. A socketpair replaces binding a
listener; DirectChannel adapts the console transport to that connected socket.
"""
import argparse,json,os,pty,select,signal,socket,struct,subprocess,sys,tempfile,threading,time
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from service_control import ServiceController,ServiceTransport
from controls import ControlError
from raw_telemetry import Mirror

class DirectChannel:
    """Transport over a connected socketpair; uses the real native handle()."""
    def __init__(self,connection):self.connection=connection;connection.settimeout(4);self.reader=connection.makefile('rb')
    def request(self,value,timeout):
        self.connection.sendall((json.dumps({'jsonrpc':'2.0','id':1,'method':value['method'],'params':value.get('params',{})})+'\n').encode())
        return json.loads(self.reader.readline())
    def close(self):self.reader.close();self.connection.close()

def until(check,timeout=8):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        value=check()
        if value:return value
        time.sleep(.025)
    raise AssertionError('timed out waiting for native state')

class Robot:
    def __init__(self,binary,directory,readonly=False):
        self.root=directory;self.sock=directory/'robotd.sock';self.stop=threading.Event();self.frames=[];self.writes=[];self.rounds=0
        self.master,self.slave=pty.openpty();port=os.ttyname(self.slave)
        (directory/'robotd.toml').write_text('[bus]\nprotocol="feetech"\nport='+json.dumps(port)+'\nfeetech_calibration='+json.dumps(str(directory/'calibration.toml'))+'\n[control]\nhz=50\n')
        self.worker=threading.Thread(target=self.emulate,daemon=True);self.worker.start()
        self.log=(directory/('readonly.log' if readonly else f'robotd-{time.monotonic_ns()}.log')).open('wb')
        client,server=socket.socketpair();self.raw_socket,raw_server=socket.socketpair()
        self.proc=subprocess.Popen([str(binary),str(directory/'robotd.toml'),str(server.fileno()),str(raw_server.fileno()),
                                    'readonly' if readonly else 'commissioning'],pass_fds=(server.fileno(),raw_server.fileno()),stdout=self.log,stderr=subprocess.STDOUT)
        server.close();raw_server.close()
        self.transport=ServiceTransport(None,str(self.sock))
        self.transport.channel=DirectChannel(client)
    def emulate(self):
        buffer=bytearray()
        try:
            while not self.stop.is_set():
                if not select.select([self.master],[],[],.05)[0]:continue
                buffer.extend(os.read(self.master,4096))
                while len(buffer)>=4:
                    if buffer[:2]!=b'\xff\xff':del buffer[0];continue
                    size=buffer[3]+4
                    if len(buffer)<size:break
                    frame=bytes(buffer[:size]);del buffer[:size]
                    assert sum(frame[2:])&255==255,'invalid outgoing checksum'
                    ident,inst=frame[2],frame[4];p=frame[5:-1]
                    def reply(id,data):
                        body=bytes([id,len(data)+2,0])+bytes(data)
                        return b'\xff\xff'+body+bytes([(~sum(body))&255])
                    if inst==0x83:self.writes.append(frame);continue
                    if inst==0x82:
                        address,length=p[:2];ids=list(p[2:]);lost=[]
                        if (address,length)==(56,15):
                            self.rounds+=1;self.frames.append(ids)
                            if self.rounds<=14:lost=[10,12]
                        answer=bytearray()
                        for id in ids:
                            if id in lost:continue
                            data=bytearray(length)
                            if (address,length)==(56,15):
                                if id==200:data[12]=self.rounds%256
                                else:data[1]=8;data[6]=74;data[7]=24
                            answer.extend(reply(id,data))
                        os.write(self.master,answer)
                    elif inst==2:
                        data=bytes([6,0,0,0,242]) if ident==200 and p[:2]==bytes([0,5]) else bytes(p[1])
                        os.write(self.master,reply(ident,data))
        except OSError:
            if not self.stop.is_set():raise
    def raw_bus(self):
        values=[];mirror=Mirror(values.append)
        with self.raw_socket as s:
            s.settimeout(4);s.sendall(b'{"jsonrpc":"2.0","id":1,"method":"robot.rawSubscribe","params":{}}\n')
            with s.makefile('rb') as f:
                ack=json.loads(f.readline());assert ack.get('result',{}).get('accepted'),ack
                for _ in range(80):
                    header=f.read(4);assert len(header)==4
                    size=struct.unpack('<I',header)[0];frame=header+f.read(size)
                    mirror.accept(frame)
                    for value in values:
                        b=value.get('data',{})
                        if value.get('channel')=='bus' and b.get('device_communication',{}).get('by_id',{}).get('10',{}).get('timeout',0)>10:return b
                    values.clear()
        raise AssertionError('no typed commissioning report in raw stream')
    def controller(self,bus):
        return ServiceController(SimpleNamespace(snapshot=lambda:{'bus':bus,'channels':{'bus':{'status':'live'}}}),transport=self.transport,warm=False)
    def close(self):
        self.transport.channel.close();self.raw_socket.close()
        try:self.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:self.proc.kill();self.proc.wait()
        self.stop.set();self.worker.join(1);os.close(self.master);os.close(self.slave);self.log.close()

def main():
    p=argparse.ArgumentParser();p.add_argument('binary',type=Path);p.add_argument('--before',action='store_true');args=p.parse_args()
    with tempfile.TemporaryDirectory(prefix='microduck-v309-') as tmp:
        directory=Path(tmp);robot=Robot(args.binary,directory)
        try:
            raw=robot.raw_bus();direct=robot.transport.read_order_status()
            if args.before:
                assert raw['read_order']['applied'] and raw['device_communication']['by_id']['10']['timeout']>10
                assert direct['phase'] in ('configuring_bus','waiting_for_bus') and 'read_order' not in direct,direct
                try:robot.transport.call({'action':'read-order-last','id':10,'session':raw['device_communication']['session'],'revision':0})
                except ControlError as e:assert '当前没有可换序的实时标定或运动服务' in str(e)
                else:raise AssertionError('old commissioning guard unexpectedly allowed reorder')
                result={'passed':True,'old_rpc_phase':direct['phase'],'raw_has_order':True,'raw_id10_timeout':raw['device_communication']['by_id']['10']['timeout'],
                        'stale_startup_cache_reproduced':True,'commissioning_readonly_guard_reproduced':True,'physical_hardware_tested':False}
            else:
                assert direct['read_order']['applied']==robot.frames[-1]
                assert direct['device_communication']['classification']=='exclusive-v2'
                Path(__file__).with_name('native-report.json').write_text(json.dumps(direct,ensure_ascii=False,indent=2)+'\n')
                control=robot.controller(raw);writes=len(robot.writes)
                body={'id':10,'session':direct['device_communication']['session'],'revision':direct['read_order']['revision']}
                ack=control.read_order(body);assert ack['accepted'] and ack['read_order']['saved_revision']==1
                applied=until(lambda:(b if (b:=robot.transport.read_order_status())['read_order']['applied_revision']==1 else None))
                assert applied['read_order']['applied'][-1]==10 and robot.frames[-1][-1]==10
                assert len(robot.writes)==writes,'reorder must not write servo registers'
                saved=(directory/'telemetry-read-order.json').read_bytes();session=body['session']
                try:control.read_order(body)
                except ControlError:pass
                else:raise AssertionError('stale revision was accepted')
                result={'passed':True,'real_console_backend_and_native_rpc_handler':True,'direct_rpc_matches_raw_order':True,
                        'actual_uart_request_tail_changed':True,'servo_register_writes_unchanged':True,'strict_stale_revision_rejected':True}
        finally:robot.close()
        if not args.before:
            robot=Robot(args.binary,directory)
            try:
                raw=robot.raw_bus();assert robot.frames[0][-1]==10
                assert robot.transport.read_order_status()['read_order']['applied'][-1]==10 and raw['device_communication']['session']!=session
                assert (directory/'telemetry-read-order.json').read_bytes()==saved
                ack=robot.controller(raw).read_order({'id':12,
                    'session':raw['device_communication']['session'],'revision':1})
                assert ack['accepted'] and ack['read_order']['saved_revision']==2
                until(lambda:robot.transport.read_order_status()['read_order']['applied'][-1]==12)
                assert robot.frames[-1][-2:]==[10,12]
                result.update(restart_restores_first_uart_request=True,second_reorder_replaces_saved_order=True)
            finally:robot.close()
            robot=Robot(args.binary,directory,readonly=True)
            try:
                before=(directory/'telemetry-read-order.json').read_bytes()
                try:robot.transport.call({'action':'read-order-last','id':10,'session':'readonly','revision':2})
                except ControlError as e:assert '当前没有可换序' in str(e)
                else:raise AssertionError('pure read-only mode accepted reorder')
                assert (directory/'telemetry-read-order.json').read_bytes()==before
                result.update(pure_readonly_remains_blocked=True,physical_hardware_tested=False)
            finally:robot.close()
        output=Path(__file__).with_name('native-before-results.json' if args.before else 'native-ipc-results.json')
        output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
