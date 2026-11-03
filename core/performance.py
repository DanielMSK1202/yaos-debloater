"""Read-only telemetry; unavailable fields stay None."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from core.device_scanner import scan_device, parse_df


def parse_cpu(text):
    rows, total = [], None
    for m in re.finditer(r'(?m)^\s*([\d.]+)%\s+(?:(\d+)/(.+?)|TOTAL):(?=\s+[\d.]+%|\s*$)', text):
        if m[2]: rows.append({'pid':int(m[2]), 'name':m[3], 'cpu_percent':float(m[1])})
        else: total = float(m[1])
    return {'overall_percent':total, 'processes':rows, 'source':'dumpsys cpuinfo',
            'window':next((s.strip() for s in text.splitlines() if 'CPU usage from' in s), None)}


def parse_ram(text):
    raw = {m[1]:int(m[2]) for m in re.finditer(r'(?m)^(\w+):\s*(\d+)\s*kB', text)}
    result = {k:raw.get(v) for k,v in {'total_kb':'MemTotal','available_kb':'MemAvailable','free_kb':'MemFree',
        'cached_kb':'Cached','swap_total_kb':'SwapTotal','swap_free_kb':'SwapFree'}.items()}
    result['swap_used_kb'] = raw['SwapTotal']-raw['SwapFree'] if {'SwapTotal','SwapFree'} <= raw.keys() else None
    return result


def parse_ps(text):
    header = next((s.split() for s in text.splitlines() if 'PID' in s.split()), [])
    name = next((k for k in ('NAME','CMD','COMMAND','ARGS') if k in header), None)
    if not name: return []
    rows = []
    for line in text.splitlines():
        parts = line.split()
        try:
            rows.append({'pid':int(parts[header.index('PID')]), 'name':parts[header.index(name)],
                         'rss_kb':int(parts[header.index('RSS')]) if 'RSS' in header else None})
        except (ValueError, IndexError): pass
    return rows


def parse_pss(text):
    section = text.partition('Total PSS by process:')[2].split('\n\n',1)[0]
    return [{'pid':int(m[3]), 'name':m[2], 'pss_kb':int(m[1].replace(',',''))}
            for m in re.finditer(r'([\d,]+)K:\s+(.+?)\s+\(pid\s+(\d+)', section)]


def bottlenecks(samples):
    findings = []
    def add(kind, explanation, evidence): findings.append(dict(kind=kind, explanation=explanation, evidence=evidence))
    recent = samples[-3:]
    if len(recent)==3:
        if all(s['cpu'].get('overall_percent') is not None and s['cpu']['overall_percent']>=80 for s in recent):
            add('cpu','CPU ≥80% in three consecutive observations. Inspect measured processes.',[s['cpu'] for s in recent])
        if all(s['ram'].get('total_kb') and s['ram'].get('available_kb') is not None and s['ram']['available_kb']/s['ram']['total_kb']<.1 for s in recent):
            add('memory','Available RAM below 10% in three observations: possible memory pressure. Cache is reclaimable.',[s['ram'] for s in recent])
        for observed in recent[0]['cpu']['processes']:
            rows = [next((r for r in s['cpu']['processes'] if r['name']==observed['name'] and r['pid']==observed['pid']),None) for s in recent]
            if all(r and r['cpu_percent']>=20 for r in rows): add('process_cpu','Process CPU ≥20% in three observations; investigate workload.',rows)
        for name in {r['name'] for r in recent[0]['processes']}:
            groups = [[r for r in s['processes'] if r['name']==name] for s in recent]
            if all(len(g)==1 for g in groups):
                rows = [g[0] for g in groups]
                changed = len({r['pid'] for r in rows})==3
                add('possible_restarts' if changed else 'persistent_process',
                    'PID changed each observation: possible restarts or separate instances.' if changed else 'Process present in three observations; persistence alone is not unnecessary work.',rows)
    if samples:
        s = samples[-1]
        if s['storage'].get('used_percent',0)>=90: add('storage','/data ≥90% used. Investigate storage usage.',s['storage'])
        for row in s['processes']:
            if row.get('rss_kb') and s['ram'].get('total_kb') and row['rss_kb']/s['ram']['total_kb']>=.1:
                add('rss','Large measured RSS (≥10% of total RAM); shared pages may inflate RSS. Inspect PSS.',row)
    return findings


class PerformanceSession:
    def __init__(self, adb, serial):
        self.adb, self.serial = adb, serial
        self.device, self.services = None, None
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.samples = []

    def sample(self):
        errors = []
        def read(*args):
            try: return self.adb.shell(self.serial,*args)
            except Exception as exc:
                errors.append({'command':' '.join(args),'error':str(exc)})
                return ''
        if self.device is None: self.device = scan_device(self.adb,self.serial)
        else:
            fp = read('getprop','ro.build.fingerprint').strip()
            if not fp or fp!=self.device.get('fingerprint'): raise RuntimeError('Device identity changed or unavailable; start a new session.')
        cpu = parse_cpu(read('dumpsys','cpuinfo'))
        processes = parse_ps(read('ps','-A','-o','PID,NAME,RSS'))
        if not processes: processes = parse_ps(read('ps','-A'))
        detailed = len(self.samples)%6==0
        pss = parse_pss(read('dumpsys','meminfo')) if detailed else None
        if detailed and not pss:
            pss = None
            errors.append({'command':'dumpsys meminfo','error':'Process PSS unavailable or unsupported format'})
        if not processes: errors.append({'command':'ps','error':'Process inventory unavailable or unsupported format'})
        if detailed: self.services = {'timestamp':datetime.now(timezone.utc).isoformat(),'raw':read('dumpsys','activity','services') or None}
        sample = dict(timestamp=datetime.now(timezone.utc).isoformat(),cpu=cpu,
            ram=parse_ram(read('cat','/proc/meminfo')),processes=processes,
            process_count=len(processes) if processes else None,pss=pss,
            storage=parse_df(read('df','/data')),errors=errors)
        if cpu['overall_percent'] is None: errors.append({'command':'dumpsys cpuinfo','error':'CPU unavailable or unsupported format'})
        self.samples.append(sample)
        return sample

    def report(self):
        return dict(schema_version=1,kind='yaos-performance',mode='read-only',device=self.device,
            started_at=self.started_at,samples=self.samples,services=self.services,findings=bottlenecks(self.samples),
            limitations=['CPU uses dumpsys reported windows, which may overlap; sustained flags require three observations.',
                'RSS includes shared pages; PSS apportions shared pages. Neither equals available RAM.',
                'Cached RAM is reclaimable, not wasted. Services and persistence do not imply unnecessary work.',
                'PID changes are possible restarts, not proof of crashes; names can be ambiguous.',
                'Sampling adds load. Session differences do not establish causes or promise improvements.'])

    def save(self,path): Path(path).write_text(json.dumps(self.report(),ensure_ascii=False,indent=2),encoding='utf-8')


def compare_reports(first,second):
    def summary(report):
        if report.get('kind')!='yaos-performance' or not isinstance(report.get('samples'),list): raise ValueError('Select performance session reports.')
        def mean(values):
            values = [v for v in values if isinstance(v,(int,float))]
            return sum(values)/len(values) if values else None
        return dict(samples=len(report['samples']),mean_cpu_percent=mean([s['cpu'].get('overall_percent') for s in report['samples']]),
            mean_available_kb=mean([s['ram'].get('available_kb') for s in report['samples']]))
    return dict(first=summary(first),second=summary(second),same_profile=all(first.get('device',{}).get(k) and first['device'][k]==second.get('device',{}).get(k) for k in ('manufacturer','model','android_version','fingerprint')),
        note='Workloads, duration and sampling windows affect comparison; differences do not prove causation.')
