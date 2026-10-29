"""Behavior tests use synthetic metadata and a fake MMIO device, never a board."""
from pathlib import Path
import csv,copy,json,struct,sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import pynq_common as c
import run_contract as runtime

def write_bit(path,part='7z020clg400'):
    head=struct.pack('>H',9)+b'\x0f\xf0\x0f\xf0\x0f\xf0\x0f\xf0\x00'+struct.pack('>H',1)
    for tag,value in [('a','mock_only'),('b',part),('c','2026/10/24'),('d','00:00:00')]:
        v=value.encode()+b'\0';head+=tag.encode()+struct.pack('>H',len(v))+v
    path.write_bytes(head+b'e'+struct.pack('>I',4)+b'MOCK')

def write_hwh(path,device='7z020',package='clg400'):
    import xml.etree.ElementTree as E
    root=E.Element('EDKSYSTEM',VIVADOVERSION='mock')
    E.SubElement(root,'SYSTEMINFO',DEVICE=device,PACKAGE=package,SPEEDGRADE='-1',NAME='mock_only')
    mods=E.SubElement(root,'MODULES')
    for name,vlnv in [('dma_in','xilinx.com:ip:axi_dma:7.1'),('dma_b','xilinx.com:ip:axi_dma:7.1'),('dma_out','xilinx.com:ip:axi_dma:7.1'),('control','xilinx.com:user:mock_control:1.0')]:
        m=E.SubElement(mods,'MODULE',FULLNAME='/'+name,INSTANCE=name,VLNV=vlnv);ps=E.SubElement(m,'PARAMETERS')
        pars={'C_BASEADDR':'0x40000000','C_HIGHADDR':'0x40000fff'}
        if name!='control':pars.update(C_INCLUDE_SG=0,C_MICRO_DMA=0,C_INCLUDE_MM2S=1,C_INCLUDE_S2MM=1,C_INCLUDE_MM2S_DRE=0,C_INCLUDE_S2MM_DRE=0,C_M_AXI_MM2S_DATA_WIDTH=64,C_M_AXI_S2MM_DATA_WIDTH=64,C_M_AXI_MM2S_ADDR_WIDTH=32,C_M_AXI_S2MM_ADDR_WIDTH=32,C_SG_LENGTH_WIDTH=16)
        for k,v in pars.items():E.SubElement(ps,'PARAMETER',NAME=k,VALUE=str(v))
    E.ElementTree(root).write(path,encoding='utf-8',xml_declaration=True)

def fixture(root,mode='loopback'):
    root.mkdir(parents=True,exist_ok=True);write_bit(root/'mock.bit');write_hwh(root/'mock.hwh')
    with (root/'a.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['index','code']);w.writerows(enumerate([1,2,3,4]))
    with (root/'b.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['index','code']);w.writerows(enumerate([10,20,30,40]))
    contract={'schema_version':1,'name':'mock_'+mode,'target_part':'xc7z020clg400-1','artifacts':{'bit':'mock.bit','hwh':'mock.hwh','sha256':{'bit':c.sha256(root/'mock.bit'),'hwh':c.sha256(root/'mock.hwh')}},'buffers':{'a':{'shape':[4],'dtype':'uint32','direction':'input','file':'a.csv'},'y':{'shape':[4],'dtype':'uint32','direction':'output'}},'registers':{},'steps':[{'kind':'dma','timeout_s':.03,'transfers':[{'ip':'dma_in','direction':'send','buffer':'a'},{'ip':'dma_out','direction':'recv','buffer':'y'}]}]}
    if mode=='vector_add':
        contract['buffers']['b']={'shape':[4],'dtype':'uint32','direction':'input','file':'b.csv'}
        contract['steps'][0]['transfers'].append({'ip':'dma_b','direction':'send','buffer':'b'})
    c.write_json(root/'contract.json',contract);return contract

class Buffer:
    def __init__(self,backend,shape,dtype):
        self.backend=backend;count,size=c.buffer_size({'shape':shape,'dtype':dtype});self.flat=[0]*count;self.nbytes=size;self.physical_address=0x1000+len(backend.buffers)*0x1000;self.freed=False
    def sync_to_device(self):self.backend.events.append(('flush',self.physical_address))
    def sync_from_device(self):self.backend.events.append(('invalidate',self.physical_address))
    def freebuffer(self):self.freed=True

class MMIO:
    def __init__(self,backend,ip):self.backend=backend;self.ip=ip;self.words={4:1,0x34:1}
    def read(self,offset):return self.words.get(offset,0)
    def write(self,offset,value):
        b=self.backend;self.words[offset]=value
        if offset in [0,0x30]:
            if value&1:self.words[offset+4]=0
            elif b.mode!='unhaltable':self.words[offset+4]=1
        if offset in [0x28,0x58]:
            base=offset-0x28;direction='send' if base==0 else 'recv';addr=self.words[base+0x18]
            buf=next(v for v in b.buffers if v.physical_address==addr);b.events.append((direction,self.ip));b.active[(self.ip,direction)]=(self,base,buf)
            b.complete()

class Backend:
    def __init__(self,mode='loopback'):self.mode=mode;self.buffers=[];self.mmios={};self.events=[];self.active={};self.loaded=False
    def load(self,bit):self.loaded=True;return {'execution_kind':'mock','fixture':'stdlib MMIO model'}
    def mmio(self,ip):
        if ip not in self.mmios:self.mmios[ip]=MMIO(self,ip)
        return self.mmios[ip]
    def allocate(self,shape,dtype):
        x=Buffer(self,shape,dtype);self.buffers.append(x);return x
    def complete(self):
        if self.mode in ['timeout','unhaltable']:return
        needed=3 if self.mode=='vector_add' else 2
        if len(self.active)!=needed:return
        send=[x for key,x in self.active.items() if key[1]=='send'];recv=[x for key,x in self.active.items() if key[1]=='recv']
        result=list(send[0][2].flat)
        if self.mode=='vector_add':result=[a+b for a,b in zip(result,send[1][2].flat)]
        for m,base,buf in recv:buf.flat[:]=result
        for m,base,buf in self.active.values():
            m.words[base+4]=2
            if self.mode=='short' and base==0x30:m.words[base+0x28]=buf.nbytes-4

class Tests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.contract=fixture(self.root)
    def tearDown(self):self.tmp.cleanup()
    def test_loopback_preserves_order_and_cache_and_ownership(self):
        b=Backend();r=runtime.run_transaction(self.root/'contract.json',self.root/'out',backend=b)
        self.assertTrue(r['passed']);self.assertFalse(r['hardware_executed']);self.assertTrue(all(x.freed for x in b.buffers))
        dma=[e for e in b.events if e[0] in ['recv','send']];self.assertEqual(dma[0][0],'recv')
        vals,_=c.read_values(self.root/'out/y.csv','integer');self.assertEqual(vals,[1,2,3,4]);self.assertTrue(any(e[0]=='invalidate' for e in b.events))
    def test_reuse_different_two_input_application(self):
        fixture(self.root,'vector_add');b=Backend('vector_add');r=runtime.run_transaction(self.root/'contract.json',self.root/'out',backend=b)
        self.assertTrue(r['passed']);self.assertEqual(c.read_values(self.root/'out/y.csv','integer')[0],[11,22,33,44])
    def test_timeout_has_bounded_halt_and_releases_only_after_ack(self):
        b=Backend('timeout');r=runtime.run_transaction(self.root/'contract.json',self.root/'out',backend=b)
        self.assertFalse(r['passed']);self.assertTrue(r['halt_confirmed']);self.assertTrue(all(x.freed for x in b.buffers))
    def test_unhaltable_dma_retains_buffers(self):
        b=Backend('unhaltable')
        with self.assertRaises(runtime.QuarantinedDMA) as caught:runtime.run_transaction(self.root/'contract.json',self.root/'out',backend=b)
        self.assertFalse(any(x.freed for x in b.buffers));self.assertTrue(caught.exception.report['buffers_retained'])
        # Only the fake device is now explicitly quiesced; no physical device is touched.
        for m in b.mmios.values():m.words[4]=1;m.words[0x34]=1
        for x in b.buffers:x.freebuffer()
        runtime._retained.remove(caught.exception)
    def test_early_tlast_short_frame_does_not_pass(self):
        r=runtime.run_transaction(self.root/'contract.json',self.root/'out',backend=Backend('short'))
        self.assertFalse(r['passed']);self.assertIn('completed 12 bytes',r['error'])
    def test_wrong_part_and_hash_stop_before_loading(self):
        for key,value in [('target_part','xc7z100ffg900-2')]:
            cc=copy.deepcopy(self.contract);cc[key]=value;c.write_json(self.root/'bad.json',cc);b=Backend()
            with self.assertRaises(c.CheckError):runtime.run_transaction(self.root/'bad.json',self.root/'out',backend=b)
            self.assertFalse(b.loaded)
        (self.root/'mock.bit').write_bytes((self.root/'mock.bit').read_bytes()[:-1]+b'X')
        with self.assertRaises(c.CheckError):runtime.run_transaction(self.root/'contract.json',self.root/'out',backend=Backend())
    def test_oversized_dma_and_sg_are_rejected(self):
        h=c.read_hwh(self.root/'mock.hwh');cc=copy.deepcopy(self.contract);cc['buffers']['a']['shape']=[16384]
        with self.assertRaises(c.CheckError):c.validate_contract(cc,h)
        h['modules']['dma_in']['parameters']['c_include_sg']='1'
        with self.assertRaises(c.CheckError):c.validate_contract(self.contract,h)
    def test_input_overflow_and_bad_index_fail(self):
        (self.root/'a.csv').write_text('index,code\n0,300\n')
        with self.assertRaises(c.CheckError):c.input_values(self.root,{'dtype':'int8','shape':[1],'file':'a.csv'})
        (self.root/'a.csv').write_text('index,code\n1,2\n')
        with self.assertRaises(c.CheckError):c.read_values(self.root/'a.csv','integer')
    def test_nonfinite_and_missing_samples_cannot_be_hidden(self):
        self.assertFalse(c.compare([1,float('nan')],[1,2],0,0)['passed'])
        self.assertIsNone(c.compare([1,float('nan')],[1,2],0,0)['mae'])
        with self.assertRaises(c.CheckError):c.compare([1],[1,2],0,0)
        with self.assertRaises(c.CheckError):c.compare([],[],0,0)
    def test_bf16_bit_decoding_and_zero_reference(self):
        p=self.root/'bf16.csv';p.write_text('index,code\n0,0x3f80\n1,0xbf80\n2,0x0000\n')
        self.assertEqual(c.read_values(p,'bf16')[0],[1,-1,0]);self.assertTrue(c.compare([0],[0],0,0)['passed'])
        self.assertIsNone(c.compare([1],[0],0,0)['relative_l2'])
    def test_quantiles_require_explicit_scope_and_keep_tail(self):
        x=c.latency_stats([1,1,1,1,1000],'us','host transaction');self.assertEqual(x['max'],1000);self.assertEqual(x['p50'],1)
        with self.assertRaises(c.CheckError):c.latency_stats([1],'us','')
    def test_register_contract_has_no_shell_actions(self):
        cc=copy.deepcopy(self.contract);cc['steps']=[{'kind':'shell','command':'anything'}]
        with self.assertRaises(c.CheckError):c.validate_contract(cc)
    def test_mock_metadata_on_another_device_is_only_offline_identity(self):
        write_bit(self.root/'mock.bit','zu3eg-sbva484');write_hwh(self.root/'mock.hwh','zu3eg','sbva484')
        r=c.inspect_pair(self.root/'mock.bit',self.root/'mock.hwh','xczu3egsbva484-1')
        self.assertEqual(r['hwh']['part'],'xczu3egsbva484-1')
    def test_realistic_report_device_speed_and_negative_slack(self):
        head='| Device : 7z020-clg400\n| Speed File : -1 PRODUCTION\n'
        timing=head+'There are 0 register/latch pins with no clock.\nWNS(ns) TNS(ns) other\n-----\n0.1 0 0 50 0.02 0 0 50 3 0 0 20\n'
        util=head+'\n'.join('| '+label+' | 1 | 0 | 0 | 100 | 1 |' for label in ['Slice LUTs','Slice Registers','Block RAM Tile','DSPs'])
        drc=head+'No DRC violations detected.\n'
        for name,data in [('t.rpt',timing),('u.rpt',util),('d.rpt',drc)]: (self.root/name).write_text(data)
        self.assertTrue(c.vivado_reports(self.root/'t.rpt',self.root/'u.rpt',self.root/'d.rpt','xc7z020clg400-1')['passed'])
        (self.root/'t.rpt').write_text(timing.replace('0.1 0 0 50','-0.1 -1 1 50'))
        self.assertFalse(c.vivado_reports(self.root/'t.rpt',self.root/'u.rpt',self.root/'d.rpt','xc7z020clg400-1')['passed'])
        (self.root/'d.rpt').write_text(head+'incomplete')
        with self.assertRaises(c.CheckError):c.vivado_reports(self.root/'t.rpt',self.root/'u.rpt',self.root/'d.rpt','xc7z020clg400-1')
    def test_keyboard_interrupt_halts_and_logs_before_reraising(self):
        class Interrupted(Backend):
            def complete(self):raise KeyboardInterrupt('notebook stop')
        b=Interrupted()
        with self.assertRaises(KeyboardInterrupt):runtime.run_transaction(self.root/'contract.json',self.root/'out',backend=b)
        report=c.read_json(self.root/'out/run.json');self.assertTrue(report['halt_confirmed']);self.assertTrue(report['interrupted']);self.assertTrue(all(x.freed for x in b.buffers))
    def test_unknown_register_window_is_not_silently_trusted(self):
        cc=copy.deepcopy(self.contract);cc['buffers']={};cc['registers']={'status':{'ip':'control','offset':2**32,'access':'r'}};cc['steps']=[{'kind':'read','register':'status'}]
        h=c.read_hwh(self.root/'mock.hwh');h['modules']['control']['parameters']={}
        with self.assertRaises(c.CheckError):c.validate_contract(cc,h)
    def test_input_snapshot_hash_is_recorded_and_changes_rejected(self):
        b=Backend();r=runtime.run_transaction(self.root/'contract.json',self.root/'out',backend=b)
        self.assertEqual(r['inputs']['a']['sha256'],c.sha256(self.root/'a.csv'))
        spec=copy.deepcopy(self.contract['buffers']['a']);spec['sha256']=c.sha256(self.root/'a.csv')
        (self.root/'a.csv').write_text('index,code\n0,100\n1,2\n2,3\n3,4\n')
        with self.assertRaises(c.CheckError):c.input_values(self.root,spec)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--json');args=p.parse_args()
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Tests);result=unittest.TextTestRunner(verbosity=2).run(suite)
    if args.json:c.write_json(args.json,{'execution_kind':'offline_mock','tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'physical_board_access':False,'passed':result.wasSuccessful()})
    sys.exit(0 if result.wasSuccessful() else 1)
