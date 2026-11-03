import unittest
from core.adb_manager import ADBManager, ADBError
from core.hardware_research import COMMANDS, collect

class HardwareResearchTests(unittest.TestCase):
    def test_fixed_probes_allowed(self):
        for c in COMMANDS:
            self.assertTrue(ADBManager._is_read_only_shell(c), c)
            self.assertIn(c[0], {'getprop','cat','ls','uname','dumpsys'})
            self.assertFalse(c[0]=='cat' and c[1].startswith('/dev/'))

    def test_unapproved_partition_reads_and_writes_blocked(self):
        a=ADBManager()
        for c in [('cat','/dev/block/mmcblk0p10'),('reboot','recovery'),('setprop','x','y'),('dd','if=/dev/block/mmcblk0')]:
            with self.assertRaises(ADBError): a.shell('fixture',*c)

    def test_disconnected_stops_before_probing(self):
        class Fake:
            def devices(self): return []
            def shell(self,*args): raise AssertionError('No probes expected')
        with self.assertRaises(RuntimeError): collect(Fake(),'fixture')
