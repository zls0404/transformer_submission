"""Portable checks and measurements. No PYNQ, NumPy or network dependency."""
from pathlib import Path
import csv, hashlib, io, json, math, re, statistics, struct
import xml.etree.ElementTree as ET

class CheckError(ValueError):
    pass

DTYPES = {'int8':1,'uint8':1,'int16':2,'uint16':2,'int32':4,'uint32':4,'float32':4,'float64':8}

def integer(value):
    if isinstance(value,bool): raise CheckError('Boolean is not an integer parameter')
    if isinstance(value,int): return value
    if isinstance(value,str):
        try: return int(value,0) if value.lower().startswith(('0x','-0x')) else int(value,10)
        except ValueError: pass
    raise CheckError(f'Invalid integer: {value!r}')

def require(condition,message):
    if not condition: raise CheckError(message)

def sha256(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()

def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def write_json(path,value):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def read_bit_header(path):
    p=Path(path)
    with p.open('rb') as f: data=f.read(65536)
    def take(pos,n):
        require(pos+n<=len(data),'Truncated or oversized .bit header')
        return data[pos:pos+n],pos+n
    raw,pos=take(0,2);n=int.from_bytes(raw,'big');_,pos=take(pos,n)
    raw,pos=take(pos,2);require(int.from_bytes(raw,'big')==1,'Unsupported .bit header; raw .bin is not accepted')
    result={}
    for expected,key in [(b'a','design'),(b'b','part'),(b'c','date'),(b'd','time')]:
        tag,pos=take(pos,1);require(tag==expected,f'Invalid .bit header field {key}')
        raw,pos=take(pos,2);length=int.from_bytes(raw,'big');text,pos=take(pos,length)
        result[key]=text.rstrip(b'\0').decode('ascii')
    tag,pos=take(pos,1);require(tag==b'e','Missing .bit payload length')
    raw,pos=take(pos,4);length=int.from_bytes(raw,'big')
    require(length>0 and p.stat().st_size==pos+length,'Bitstream payload length does not match file size')
    result.update(payload_bytes=length,sha256=sha256(p));return result

def read_hwh(path):
    root=ET.parse(path).getroot();info=root.find('SYSTEMINFO')
    require(info is not None,'Unsupported HWH: SYSTEMINFO is absent')
    a=info.attrib;require(all(a.get(k) for k in ['DEVICE','PACKAGE','SPEEDGRADE']),'Incomplete HWH target identity')
    part=('xc'+a['DEVICE']+a['PACKAGE']+a['SPEEDGRADE']).lower()
    modules={}
    for m in root.findall('.//MODULE'):
        name=m.get('FULLNAME',m.get('INSTANCE','')).strip('/')
        if not name: continue
        require(name not in modules,f'Duplicate HWH module: {name}')
        pars={p.get('NAME','').lower():p.get('VALUE','') for p in m.findall('./PARAMETERS/PARAMETER')}
        registers=[]
        for r in m.findall('.//REGISTER'):
            registers.append(dict(r.attrib))
        modules[name]={'vlnv':m.get('VLNV',''),'parameters':pars,'registers':registers}
    return {'part':part,'design':a.get('NAME'),'vivado_version':root.get('VIVADOVERSION'),'modules':modules,'sha256':sha256(path)}

def bare_part(part):
    p=part.lower().replace('xc','',1)
    return re.sub(r'[^a-z0-9]','',re.sub(r'-\d.*$','',p))

def part_key(part):
    return re.sub(r'[^a-z0-9]','',part.lower().removeprefix('xc'))

def inspect_pair(bit,hwh,expected_part,expected_hashes=None):
    b=read_bit_header(bit);h=read_hwh(hwh)
    require(part_key(h['part'])==part_key(expected_part),f'HWH target {h["part"]} != requested {expected_part}')
    require(bare_part(b['part'])==bare_part(expected_part),f'BIT target {b["part"]} != requested {expected_part}')
    require(Path(bit).stem==Path(hwh).stem,'PYNQ discovery expects matching .bit/.hwh basenames')
    if expected_hashes is not None:
        require(isinstance(expected_hashes,dict) and set(expected_hashes)=={'bit','hwh'},'Pair manifest must contain bit and hwh SHA-256')
        for key,actual in [('bit',b['sha256']),('hwh',h['sha256'])]:
            require(isinstance(expected_hashes[key],str) and re.fullmatch(r'[0-9a-fA-F]{64}',expected_hashes[key]) is not None,'Invalid SHA-256 value')
            require(actual==expected_hashes[key].lower(),f'{key} SHA-256 mismatch')
    return {'bit':b,'hwh':h,'pair_hashes_checked':expected_hashes is not None,
            'identity_limit':'Matching target/filenames alone do not establish a same-build pair; use trusted export hashes.'}

def buffer_size(spec):
    require(isinstance(spec,dict),'Buffer specification must be an object')
    require(isinstance(spec.get('dtype'),str) and spec['dtype'] in DTYPES,f'Unsupported dtype {spec.get("dtype")}')
    shape=spec.get('shape');require(isinstance(shape,list) and 1<=len(shape)<=4,'Buffer shape must have 1..4 dimensions')
    count=1
    for size in shape:
        require(isinstance(size,int) and not isinstance(size,bool) and size>0,'Shape dimensions must be positive integers')
        count*=size
    require(count*DTYPES[spec['dtype']]<=2**31,'A single buffer exceeds this runner\'s 2 GiB limit')
    return count,count*DTYPES[spec['dtype']]

def input_values(root,spec,payload=None):
    if payload is None:payload=(Path(root)/spec['file']).read_bytes()
    if 'sha256' in spec:require(hashlib.sha256(payload).hexdigest()==spec['sha256'],'Input CSV SHA-256 differs from the bound contract')
    dtype=spec['dtype'];vals,codes=read_values_text(payload.decode('utf-8-sig'),'float' if dtype.startswith('float') else 'integer')
    require(len(vals)==buffer_size(spec)[0],'Input element count differs from declared shape')
    if dtype.startswith('float'):
        require(all(math.isfinite(x) for x in vals),'Nonfinite float input requires a purpose-built numerical probe')
        if dtype=='float32':require(all(abs(x)<=3.4028234663852886e38 for x in vals),'Input exceeds float32 range')
        return vals
    bits=8*DTYPES[dtype];low=0 if dtype.startswith('u') else -(1<<(bits-1));high=(1<<bits)-1 if dtype.startswith('u') else (1<<(bits-1))-1
    require(all(low<=x<=high for x in codes),f'Input would overflow {dtype}; quantize explicitly before transfer')
    return codes

def dma_properties(module,direction):
    require(module['vlnv'].startswith('xilinx.com:ip:axi_dma:'),'Runner supports AXI DMA only, not VDMA/CDMA/MCDMA')
    p=module['parameters']
    def par(k):
        require(k in p,f'Missing DMA parameter {k}')
        return integer(p[k])
    require(par('c_include_sg')==0,'Scatter-Gather DMA needs a separate runner')
    require(par('c_micro_dma')==0,'Micro DMA is not supported by this runner')
    suffix='mm2s' if direction=='send' else 's2mm'
    require(par('c_include_'+suffix)==1,f'DMA {direction} channel is disabled')
    bits=par('c_sg_length_width');require(1<=bits<=26,'Invalid DMA length width')
    width=par('c_m_axi_'+suffix+'_data_width');require(width>0 and width%8==0,'Invalid DMA memory width')
    addr_key='c_m_axi_'+suffix+'_addr_width'
    addr=integer(p[addr_key]) if addr_key in p else par('c_addr_width')
    return dict(max_bytes=(1<<bits)-1,alignment=width//8,dre=bool(par('c_include_'+suffix+'_dre')),address_bits=addr)

def validate_contract(contract,metadata=None):
    require(isinstance(contract,dict),'Contract root must be an object')
    require(type(contract.get('schema_version')) is int and contract['schema_version']==1,'Only contract schema_version 1 is supported')
    require(isinstance(contract.get('name'),str) and contract['name'],'Contract needs a name')
    require(isinstance(contract.get('target_part'),str) and contract['target_part'],'Contract needs target_part')
    art=contract.get('artifacts',{});require(isinstance(art,dict) and all(isinstance(art.get(k),str) and art[k] for k in ['bit','hwh']),'Declare bit and hwh paths')
    buffers=contract.get('buffers',{});require(isinstance(buffers,dict),'buffers must be an object')
    for name,spec in buffers.items():
        require(re.fullmatch(r'[a-z][a-z0-9_]*',name) is not None,'Use simple lowercase buffer names')
        count,size=buffer_size(spec)
        require(spec.get('direction') in ['input','output'],'Buffer direction must be input or output')
        if spec['direction']=='input': require(isinstance(spec.get('file'),str) and spec['file'],'Input buffer needs a CSV file')
    registers=contract.get('registers',{})
    require(isinstance(registers,dict),'registers must be an object')
    for name,r in registers.items():
        require(isinstance(r,dict),'Register specification must be an object')
        require(isinstance(r.get('ip'),str) and r['ip'],'Register requires an IP instance')
        offset=integer(r.get('offset'));require(offset>=0 and offset%4==0,'MMIO register offset must be nonnegative and 4-byte aligned')
        require(r.get('access') in ['r','w','rw'],'Register access must be r, w, or rw')
        if metadata:
            require(r['ip'] in metadata['modules'],f'Missing register IP {r["ip"]}')
            pars=metadata['modules'][r['ip']]['parameters']
            windows=[]
            for key,value in pars.items():
                if key.endswith('baseaddr') and key[:-8]+'highaddr' in pars:
                    low=integer(value);high=integer(pars[key[:-8]+'highaddr']);require(high>=low,'Invalid HWH register window')
                    windows.append((low,high))
            require(len(windows)==1,'HWH must identify one register window; missing/ambiguous range needs an explicit design-specific adapter')
            require(offset+4<=windows[0][1]-windows[0][0]+1,'Register outside HWH address range')
    steps=contract.get('steps');require(isinstance(steps,list) and steps,'Contract needs ordered steps')
    seen_buffers=set()
    for step in steps:
        require(isinstance(step,dict),'Each step must be an object')
        kind=step.get('kind')
        require(kind in ['write','read','poll','dma'],f'Unsupported step kind {kind}; no shell/eval actions are allowed')
        if kind!='dma':
            reg=step.get('register');require(reg in registers,f'Unknown register {reg}')
            access=registers[reg]['access']
            require(('w' if kind=='write' else 'r') in access,'Register access violation')
            if kind=='write': require(0<=integer(step.get('value'))<2**32,'MMIO write must be uint32')
            if kind=='poll':
                mask=integer(step.get('mask'));expected=integer(step.get('equals'))
                require(0<mask<2**32 and expected>=0 and expected&~mask==0,'Invalid poll mask/equality')
        else:
            transfers=step.get('transfers');require(isinstance(transfers,list) and transfers,'DMA step needs transfers')
            channels=set()
            for t in transfers:
                require(isinstance(t,dict),'Each DMA transfer must be an object')
                require(t.get('direction') in ['send','recv'],'DMA direction must be send or recv')
                require(t.get('buffer') in buffers,'Unknown DMA buffer')
                require(t.get('ip') and isinstance(t['ip'],str),'DMA transfer requires IP instance')
                key=(t['ip'],t['direction']);require(key not in channels,'Same DMA channel cannot run two buffers concurrently');channels.add(key)
                name=t['buffer'];spec=buffers[name];require((spec['direction']=='input')==(t['direction']=='send'),'Buffer direction disagrees with DMA')
                require(name not in seen_buffers,'Each buffer has one owner/transfer per run; use a new buffer name for another stage');seen_buffers.add(name)
                if metadata:
                    require(t['ip'] in metadata['modules'],f'Missing DMA {t["ip"]}')
                    cap=dma_properties(metadata['modules'][t['ip']],t['direction'])
                    require(buffer_size(spec)[1]<=cap['max_bytes'],f'{name}: transfer exceeds DMA BTT maximum {cap["max_bytes"]} bytes; do not split TLAST frames silently')
        if kind in ['poll','dma']:
            timeout=step.get('timeout_s');require(isinstance(timeout,(int,float)) and not isinstance(timeout,bool) and math.isfinite(timeout) and 0<timeout<=3600,'Explicit timeout_s must be in (0, 3600]')
    require(seen_buffers==set(buffers),'Every buffer must be used exactly once by the transaction')
    if metadata: require(part_key(metadata['part'])==part_key(contract['target_part']),'Contract target disagrees with HWH')
    return {'name':contract['name'],'steps':len(steps),'buffers':{k:dict(elements=buffer_size(v)[0],bytes=buffer_size(v)[1]) for k,v in buffers.items()},'hardware_executed':False}

def read_values(path,encoding='float',fraction_bits=0):
    return read_values_text(Path(path).read_text(encoding='utf-8-sig'),encoding,fraction_bits)

def read_values_text(text,encoding='float',fraction_bits=0):
    require(encoding in ['float','integer','bf16'],'Encoding must be float, integer or bf16')
    require(isinstance(fraction_bits,int) and -64<=fraction_bits<=64,'fraction_bits must be in [-64,64]')
    values=[];codes=[]
    with io.StringIO(text,newline='') as f:
        reader=csv.DictReader(f);require(reader.fieldnames is not None,'CSV has no header')
        require(len(set(reader.fieldnames))==len(reader.fieldnames),'CSV header columns must be unique')
        col='code' if encoding in ['integer','bf16'] else 'value'
        require('index' in reader.fieldnames and col in reader.fieldnames,f'CSV requires index,{col}')
        for i,row in enumerate(reader):
            require(integer(row['index'])==i,'Indices must start at 0 and be contiguous, ordered and unique')
            if encoding=='float': v=float(row[col]);codes.append(None)
            else:
                c=integer(row[col]);codes.append(c)
                if encoding=='bf16':
                    require(0<=c<=65535,'BF16 code must be uint16');v=struct.unpack('>f',struct.pack('>I',c<<16))[0]
                else:v=c*2.0**(-fraction_bits)
            values.append(v)
    require(values,'Empty CSV is not a valid measurement');return values,codes

def compare(actual,reference,atol,rtol):
    require(all(math.isfinite(v) and v>=0 for v in [atol,rtol]),'Tolerances must be finite and nonnegative')
    require(len(actual)==len(reference),'Different element counts: no truncation, padding or filtering')
    require(actual,'Cannot compare empty arrays')
    bad=[i for i,(a,b) in enumerate(zip(actual,reference)) if not (math.isfinite(a) and math.isfinite(b))]
    if bad:return {'passed':False,'elements':len(actual),'nonfinite_indices':bad,'mae':None,'rmse':None,'max_abs':None,'relative_l2':None,'reason':'Nonfinite samples retained; aggregate numerical error is undefined.'}
    errors=[a-b for a,b in zip(actual,reference)]
    if not all(math.isfinite(x) for x in errors):
        return {'passed':False,'elements':len(actual),'nonfinite_indices':[],'mae':None,'rmse':None,'max_abs':None,'relative_l2':None,'reason':'Finite inputs overflowed the error arithmetic; use a suitable numerical range.'}
    fails=[i for i,(e,b) in enumerate(zip(errors,reference)) if abs(e)>atol+rtol*abs(b)]
    scale=max(max(map(abs,reference)),max(map(abs,errors))) or 1.0
    norm=math.hypot(*(x/scale for x in reference));errnorm=math.hypot(*(x/scale for x in errors))
    return dict(passed=not fails,elements=len(errors),failed_indices=fails,nonfinite_indices=[],atol=atol,rtol=rtol,
                mae=math.fsum(abs(x)/len(errors) for x in errors),rmse=math.hypot(*(x/math.sqrt(len(errors)) for x in errors)),max_abs=max(map(abs,errors)),
                relative_l2=errnorm/norm if norm else (0.0 if errnorm==0 else None),relative_l2_defined=bool(norm or errnorm==0))

def percentile(values,q):
    vals=sorted(values);pos=(len(vals)-1)*q;lo=int(pos);hi=min(lo+1,len(vals)-1)
    return vals[lo]+(vals[hi]-vals[lo])*(pos-lo)

def latency_stats(values,unit,scope):
    require(unit in ['ns','us','ms','s'],'Declare a supported latency unit')
    require(isinstance(scope,str) and scope.strip(),'Timing scope is required')
    require(values and all(math.isfinite(x) and x>=0 for x in values),'Latency samples must be nonempty, finite and nonnegative')
    return dict(count=len(values),unit=unit,scope=scope,min=min(values),mean=statistics.fmean(values),std=statistics.pstdev(values),
                p50=percentile(values,.5),p95=percentile(values,.95),p99=percentile(values,.99),max=max(values),
                percentile_method='linear interpolation, index=(n-1)*q',tail_sample_note='P99 is weakly supported with fewer than 100 samples' if len(values)<100 else None)

def vivado_reports(timing,utilization,drc,expected_part):
    tx=Path(timing).read_text(encoding='utf-8-sig',errors='strict');ux=Path(utilization).read_text(encoding='utf-8-sig',errors='strict');dx=Path(drc).read_text(encoding='utf-8-sig',errors='strict')
    for label,text in [('timing',tx),('utilization',ux),('drc',dx)]:
        dev=re.search(r'^\| Device\s*:\s*(\S+)',text,re.M);require(dev is not None,f'{label}: device missing')
        require(bare_part(dev.group(1))==bare_part(expected_part),f'{label}: wrong target device')
        expected_grade=re.search(r'-(\d[a-zA-Z]?)',expected_part)
        actual_grade=re.search(r'-(\d[a-zA-Z]?)',dev.group(1))
        if actual_grade is None:
            actual_grade=re.search(r'^\| Speed File\s*:\s*-(\d[a-zA-Z]?)',text,re.M)
        require(expected_grade is not None and actual_grade is not None,'Speed grade is not stated in the report')
        require(expected_grade.group(1).lower()==actual_grade.group(1).lower(),f'{label}: wrong speed grade')
    at=tx.find('WNS(ns)');require(at>=0,'Timing summary table is missing')
    vals=None
    for line in tx[at:].splitlines()[1:8]:
        cols=line.split()
        if len(cols)==12:
            try:vals=[float(x) for x in cols];break
            except ValueError:pass
    require(vals is not None,'Unsupported or incomplete timing summary')
    wns,tns,setup_failing,_,whs,ths,hold_failing,_,wpws,tpws,pulse_failing,_=vals
    items={}
    for key,labels in [('lut',['Slice LUTs','CLB LUTs']),('ff',['Slice Registers','CLB Registers']),('bram36',['Block RAM Tile']),('dsp',['DSPs'])]:
        match=None
        for label in labels:
            match=re.search(r'^\|\s*'+re.escape(label)+r'\s*\|([^\n]+)',ux,re.M)
            if match is not None:break
        require(match is not None,f'Missing utilization {labels}')
        cols=[x.strip() for x in match.group(1).split('|')]
        require(len(cols)>=4,f'Incomplete resource row {label}')
        used=float(cols[0]);avail=float(cols[3]);require(math.isfinite(used) and math.isfinite(avail) and avail>0 and used>=0,'Resource count/capacity is invalid')
        items[key]={'used':used,'available':avail,'percent':100*used/avail}
    summaries=re.findall(r'^\|\s*[^|]+\|\s*(Critical Warning|Warning|Error|Advisory)\s*\|[^|]+\|\s*(\d+)\s*\|',dx,re.M)
    if not summaries:
        require(re.search(r'No DRC violations|0 DRC violations',dx,re.I) is not None,'DRC summary is missing or unsupported')
    sev={k:sum(int(v) for s,v in summaries if s==k) for k in ['Error','Critical Warning','Warning','Advisory']}
    noclock=re.search(r'There are (\d+) register/latch pins with no clock',tx)
    no_clock_count=int(noclock.group(1)) if noclock else None
    timing_ok=wns>=0 and whs>=0 and wpws>=0 and tns==0 and ths==0 and tpws==0 and setup_failing==hold_failing==pulse_failing==0
    ok=timing_ok and sev['Error']==0 and no_clock_count==0 and all(x['used']<=x['available'] for x in items.values())
    return dict(passed=ok,part=expected_part,wns_ns=wns,whs_ns=whs,wpws_ns=wpws,tns_ns=tns,ths_ns=ths,tpws_ns=tpws,no_clock_registers=no_clock_count,
                resources=items,drc=sev,scope='Static timing/resource/DRC checks only; not hardware functional validation',source_sha256={k:sha256(p) for k,p in [('timing',timing),('utilization',utilization),('drc',drc)]})
