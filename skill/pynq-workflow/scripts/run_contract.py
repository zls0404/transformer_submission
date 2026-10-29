"""Notebook API for ordered MMIO / simple AXI DMA transactions on PYNQ.

Importing this module performs no hardware access. Uses PYNQ MMIO/allocate,
not the DMA driver's unbounded start/wait loops. See references/runtime.md.
"""
from pathlib import Path
import csv,platform,time
from pynq_common import *

_retained=[]

class QuarantinedDMA(RuntimeError):
    """Hardware did not confirm halt; buffers are retained for explicit recovery."""
    def __init__(self,message,buffers,mmios,report):
        super().__init__(message);self.buffers=buffers;self.mmios=mmios;self.report=report

class PynqBackend:
    def load(self,bit):
        import pynq
        self.pynq=pynq
        # Metadata discovery first; callers have already validated target and hashes.
        self.overlay=pynq.Overlay(str(bit),download=False)
        self.overlay.download()
        return {'execution_kind':'physical_pynq','pynq_version':pynq.__version__,'kernel':platform.release(),'machine':platform.machine()}
    def mmio(self,ip):
        require(ip in self.overlay.ip_dict,f'IP not present in PYNQ ip_dict: {ip}')
        d=self.overlay.ip_dict[ip]
        return self.pynq.MMIO(d['phys_addr'],d['addr_range'])
    def allocate(self,shape,dtype):
        return self.pynq.allocate(shape=tuple(shape),dtype=dtype)

def _wait(predicate,deadline,message):
    while True:
        if predicate():return
        if time.monotonic()>=deadline:raise TimeoutError(message)
        time.sleep(.0002)

def _sync(buf,to_device):
    f=getattr(buf,'sync_to_device' if to_device else 'sync_from_device',None)
    if f is None:f=getattr(buf,'flush' if to_device else 'invalidate')
    f()

def _free(buffers):
    for b in buffers.values():b.freebuffer()

def _statuses(channels):
    return [{'ip':ip,'direction':direction,'status_hex':f'0x{mmio.read(base+4):08x}'} for (ip,direction),(mmio,base) in channels.items()]

def _halt(channels,timeout_s=.25):
    # Clear run/stop without an unbounded driver stop(); no global DMA/PL reset.
    try:
        for mmio,base in channels.values():mmio.write(base,mmio.read(base)&~1)
        _wait(lambda:all(mmio.read(base+4)&1 for mmio,base in channels.values()),time.monotonic()+timeout_s,'DMA halt acknowledgement timeout')
        return True
    except BaseException:return False

def run_transaction(contract_path,output_dir,artifact_root=None,backend=None):
    """Execute one explicit transaction; reprograms PL once per invocation.

    Only call when overlay loading / MMIO / DMA is within the user's scope.
    An unhalted error retains buffers and raises QuarantinedDMA. Keep that
    exception and the Python process alive until board-specific recovery.
    """
    path=Path(contract_path).resolve();contract=read_json(path);validate_contract(contract)
    root=Path(artifact_root).resolve() if artifact_root else path.parent
    art=contract['artifacts']
    require('sha256' in art,'Hardware execution requires trusted same-build bit/hwh hashes in the contract')
    pair=inspect_pair(root/art['bit'],root/art['hwh'],contract['target_part'],art['sha256'])
    require(backend is not None or pair['bit']['payload_bytes']>=1024,'Synthetic/tiny bitstream is not accepted for physical hardware')
    plan=validate_contract(contract,pair['hwh'])
    inputs={};input_records={}
    for name,spec in contract.get('buffers',{}).items():
        if spec['direction']!='input':continue
        payload=(root/spec['file']).read_bytes();inputs[name]=input_values(root,spec,payload)
        input_records[name]={'file':spec['file'],'sha256':hashlib.sha256(payload).hexdigest(),'file_bytes':len(payload)}
    out=Path(output_dir).resolve();require(not out.exists(),'Use a new output directory for each hardware run')
    out.mkdir(parents=True)
    backend=backend or PynqBackend();buffers={};mmios={};channels={};completed=set()
    report={'name':contract['name'],'target_part':contract['target_part'],'contract_sha256':sha256(path),'pair_sha256':{'bit':pair['bit']['sha256'],'hwh':pair['hwh']['sha256']},'hardware_executed':False,'steps':[],'plan':plan,'passed':False}
    report['inputs']=input_records
    host_start=time.perf_counter_ns()
    try:
        report['environment']=backend.load(root/art['bit']);report['hardware_executed']=report['environment'].get('execution_kind')=='physical_pynq'
        for name,spec in contract.get('buffers',{}).items():
            b=backend.allocate(spec['shape'],spec['dtype']);buffers[name]=b
            require(b.nbytes==buffer_size(spec)[1],f'{name}: allocated byte count differs from contract')
            if spec['direction']=='input':
                for i,v in enumerate(inputs[name]):b.flat[i]=v
            else:
                for i in range(buffer_size(spec)[0]):b.flat[i]=0
            # Flush output initialization too, so dirty CPU lines cannot overwrite DMA data.
            _sync(b,True)
        def mmio_for(ip):
            if ip not in mmios:mmios[ip]=backend.mmio(ip)
            return mmios[ip]
        def register(spec):
            return mmio_for(spec['ip']),integer(spec['offset'])
        transaction_start=time.perf_counter_ns()
        for number,step in enumerate(contract['steps']):
            begin=time.perf_counter_ns();rec={'index':number,'kind':step['kind']};report['steps'].append(rec)
            kind=step['kind']
            if kind in ['write','read','poll']:
                m,offset=register(contract['registers'][step['register']]);rec['register']=step['register']
                if kind=='write':m.write(offset,integer(step['value']))
                elif kind=='read':rec['value']=int(m.read(offset))
                else:
                    mask=integer(step['mask']);value=integer(step['equals'])
                    def done():
                        rec['last_value']=int(m.read(offset));return rec['last_value']&mask==value
                    _wait(done,time.monotonic()+step['timeout_s'],f'Register poll timeout: {step["register"]}')
            else:
                deadline=time.monotonic()+step['timeout_s'];active=[]
                # The simultaneous stage arms every receiver before any sender.
                transfers=sorted(step['transfers'],key=lambda t:t['direction']!='recv')
                for t in transfers:
                    ip=t['ip'];direction=t['direction'];name=t['buffer'];buf=buffers[name]
                    cap=dma_properties(pair['hwh']['modules'][ip],direction)
                    addr=int(buf.physical_address);require(addr>=0 and addr+buf.nbytes<=(1<<cap['address_bits']),'Allocated buffer is outside DMA address width')
                    require(cap['dre'] or addr%cap['alignment']==0,'DMA buffer address is not aligned and DRE is disabled')
                    m=mmio_for(ip);base=0 if direction=='send' else 0x30;status=m.read(base+4)
                    require(status&0x70==0,f'{ip}/{direction}: DMA is in an error state')
                    require(status&3!=0,f'{ip}/{direction}: DMA is busy before transfer')
                    channels[(ip,direction)]=(m,base)
                    m.write(base,1)
                    _wait(lambda:m.read(base+4)&1==0,deadline,f'{ip}/{direction}: DMA start timeout')
                    m.write(base+0x18,addr&0xffffffff);m.write(base+0x1c,(addr>>32)&0xffffffff)
                    m.write(base+0x28,buf.nbytes);active.append((t,m,base,buf.nbytes))
                def done_dma():
                    idle=True
                    for t,m,base,nbytes in active:
                        s=m.read(base+4)
                        if s&0x70:raise RuntimeError(f'{t["ip"]}/{t["direction"]}: DMA error status 0x{s:08x}')
                        if s&1:raise RuntimeError(f'{t["ip"]}/{t["direction"]}: unexpected halt')
                        idle=idle and bool(s&2)
                    return idle
                _wait(done_dma,deadline,'DMA completion timeout; inspect TLAST, lengths, backpressure and reset sequencing')
                rec['transfers']=[]
                for t,m,base,nbytes in active:
                    actual=int(m.read(base+0x28))
                    require(actual==nbytes,f'{t["buffer"]}: completed {actual} bytes, expected {nbytes}')
                    if t['direction']=='recv':_sync(buffers[t['buffer']],False)
                    completed.add(t['buffer']);rec['transfers'].append({'ip':t['ip'],'direction':t['direction'],'bytes':actual})
            rec['elapsed_us']=(time.perf_counter_ns()-begin)/1000
        report['transaction_us']=(time.perf_counter_ns()-transaction_start)/1000
        report['timing_scope']='Host-observed ordered register/DMA steps including polling; excludes overlay load, allocation and CSV input/output. Not isolated PL cycles.'
        require(completed==set(buffers),'Some buffers were not transferred')
        for name,spec in contract.get('buffers',{}).items():
            if spec['direction']!='output':continue
            col='value' if spec['dtype'].startswith('float') else 'code'
            with (out/(name+'.csv')).open('w',encoding='utf-8',newline='') as f:
                w=csv.writer(f);w.writerow(['index',col]);w.writerows((i,float(v) if col=='value' else int(v)) for i,v in enumerate(buffers[name].flat))
        report['passed']=True;report['pass_scope']='Transaction and byte counts only; compare output CSV against a declared numerical reference separately.'
        _free(buffers);buffers={}
    except BaseException as error:
        report['error']=type(error).__name__+': '+str(error)
        try:report['dma_status']=_statuses(channels) if channels else []
        except BaseException as snapshot_error:report['dma_status_error']=str(snapshot_error)
        safe=_halt(channels);report['halt_confirmed']=safe
        if safe:_free(buffers);buffers={}
        else:
            report['buffers_retained']=True
            pending=QuarantinedDMA('DMA did not confirm halt. Keep the notebook process and this exception alive; do not free or reuse buffers before board-specific recovery.',buffers,mmios,report)
            _retained.append(pending);write_json(out/'run.json',report);raise pending from error
        if not isinstance(error,Exception):
            report['interrupted']=True;report['total_host_us']=(time.perf_counter_ns()-host_start)/1000
            write_json(out/'run.json',report);raise
    report['total_host_us']=(time.perf_counter_ns()-host_start)/1000
    write_json(out/'run.json',report);return report
