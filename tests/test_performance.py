"""Synthetic Android-format fixtures; automated tests never contact a TV."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from core.performance import *

class TelemetryTests(unittest.TestCase):
    def test_cpu(self):
        value=parse_cpu('CPU usage from 5000ms to 0ms ago:\n 24% 42/app: 20% user\n 81% TOTAL: 60% user')
        self.assertEqual(value['overall_percent'],81)
        self.assertEqual(value['processes'][0]['pid'],42)
        self.assertIsNone(parse_cpu('unsupported')['overall_percent'])

    def test_ram(self):
        r=parse_ram('MemTotal: 1000 kB\nMemFree: 20 kB\nMemAvailable: 100 kB\nCached: 500 kB\nSwapTotal: 200 kB\nSwapFree: 30 kB')
        self.assertEqual(r['available_kb'],100)
        self.assertEqual(r['cached_kb'],500)
        self.assertEqual(r['swap_used_kb'],170)
        self.assertIsNone(parse_ram('')['free_kb'])

    def test_process_memory(self):
        self.assertEqual(parse_ps('PID NAME RSS\n42 app 2048')[0]['rss_kb'],2048)
        self.assertIsNone(parse_ps('USER PID NAME\nu0 42 app')[0]['rss_kb'])
        self.assertEqual(parse_pss('Total PSS by process:\n 1,024K: app (pid 42)\n\nTotal PSS by category:\n 900K: Other (pid 1)'),[{'pid':42,'name':'app','pss_kb':1024}])
        self.assertEqual(parse_pss('unsupported'),[])

    def sample(self,cpu=90,available=50,pid=42):
        return dict(timestamp='fixture',cpu={'overall_percent':cpu,'processes':[{'pid':pid,'name':'app','cpu_percent':25}]},
            ram={'total_kb':1000,'available_kb':available},processes=[{'pid':pid,'name':'app','rss_kb':200}],storage={'used_percent':95})

    def test_repeated_pressure_and_restarts(self):
        data=[self.sample(pid=p) for p in (42,43,44)]
        kinds={f['kind'] for f in bottlenecks(data)}
        self.assertTrue({'cpu','memory','storage','rss','possible_restarts'}<=kinds)
        self.assertNotIn('process_cpu',kinds)
        self.assertIn('process_cpu',{f['kind'] for f in bottlenecks([self.sample() for _ in range(3)])})
        self.assertNotIn('cpu',{f['kind'] for f in bottlenecks(data[:1])})
        self.assertNotIn('memory',{f['kind'] for f in bottlenecks([self.sample(available=500)]*3)})

    def test_missing_telemetry(self):
        s=self.sample(cpu=None,available=None)
        s['processes']=[]; s['storage']={}; s['cpu']['processes']=[]
        self.assertEqual(bottlenecks([s]*3),[])

    def test_session_history_report_and_comparison(self):
        class Fake:
            def shell(self,serial,*args):
                if args==('getprop','ro.build.fingerprint'): return 'fp'
                if args==('dumpsys','cpuinfo'): return ' 10% TOTAL: 5% user'
                if args==('cat','/proc/meminfo'): return 'MemTotal: 1000 kB\nMemAvailable: 500 kB'
                if args[0]=='ps': return 'PID NAME RSS\n42 app 123'
                raise RuntimeError('unsupported fixture command')
        session=PerformanceSession(Fake(),'fixture')
        with patch('core.performance.scan_device',return_value={'manufacturer':'fixture','model':'fixture','android_version':'9','fingerprint':'fp'}):
            session.sample(); session.sample()
        self.assertEqual(len(session.samples),2)
        self.assertTrue(session.samples[0]['errors'])
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'session.json'; session.save(p); report=json.loads(p.read_text())
        self.assertEqual(report['mode'],'read-only')
        result=compare_reports(report,report)
        self.assertTrue(result['same_profile'])
        self.assertEqual(result['first']['mean_cpu_percent'],10)

    def test_identity_change_stops_sampling(self):
        class Fake:
            def shell(self,*args): return 'different'
        session=PerformanceSession(Fake(),'fixture'); session.device={'fingerprint':'original'}
        with self.assertRaises(RuntimeError): session.sample()
        self.assertEqual(session.samples,[])
