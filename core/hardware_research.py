"""Fixed read-only Phase 0 probes. No block-device contents or private keys are read."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

PROPERTIES = ('ro.hardware','ro.board.platform','ro.boot.hardware','ro.product.board','ro.product.device',
    'ro.product.model','ro.product.manufacturer','ro.product.cpu.abi','ro.product.cpu.abilist',
    'ro.bootloader','ro.build.fingerprint','ro.opengles.version','ro.build.version.release',
    'ro.build.version.sdk','ro.build.version.incremental','ro.build.display.id','ro.build.version.security_patch',
    'ro.boot.flash.locked','ro.boot.verifiedbootstate','ro.boot.vbmeta.device_state','ro.boot.veritymode',
    'ro.boot.secureboot','ro.secure','ro.boot.slot_suffix','ro.boot.hardware.revision',
    'ro.revision','ro.soc.manufacturer','ro.soc.model','wifi.interface','ro.boot.wificonfig',
    'ro.vendor.bluetooth.soc','ro.sf.lcd_density','ro.build.type')
PATHS = ('/proc/cpuinfo','/proc/cmdline','/proc/meminfo','/proc/partitions','/proc/mounts',
    '/sys/firmware/devicetree/base/model','/sys/firmware/devicetree/base/compatible',
    '/proc/device-tree/model','/proc/device-tree/compatible',
    '/sys/devices/system/cpu/online','/sys/devices/system/cpu/present',
    '/sys/block/mmcblk0/device/name','/sys/block/mmcblk0/device/type','/sys/block/mmcblk0/device/manfid',
    '/sys/block/mmcblk0/size','/sys/block/mmcblk0/queue/logical_block_size',
    '/sys/class/net/wlan0/device/uevent','/sys/class/net/wlan0/device/modalias',
    '/sys/class/bluetooth/hci0/device/uevent','/proc/modules') + tuple(
    f'/sys/devices/system/cpu/cpu{i}/cpufreq/{field}' for i in range(4)
    for field in ('cpuinfo_max_freq','cpuinfo_min_freq','scaling_cur_freq','scaling_available_frequencies'))
PATHS += ('/vendor/etc/media_codecs.xml','/system/etc/media_codecs.xml', '/vendor/etc/media_codecs_performance.xml', '/proc/asound/cards','/proc/bus/input/devices', '/vendor/etc/fstab.m5621', '/sys/firmware/devicetree/base/cpus/cpu@0/compatible')
PATHS += ('/vendor/tvconfig/config/board.ini','/vendor/tvconfig/config/Board.h','/sys/bus/usb/devices/3-1/idVendor','/sys/bus/usb/devices/3-1/idProduct','/sys/bus/usb/devices/3-1/product')
COMMANDS = tuple(('getprop', p) for p in PROPERTIES) + tuple(('cat', p) for p in PATHS) + (
    ('uname','-a'), ('ls','/vendor/tvconfig/config/panel'), ('ls','/vendor/tvconfig/config/model'), ('ls','/sys/bus/usb/devices'), ('ls','/vendor/tvconfig/config'), ('ls','/vendor/etc'), ('ls','/system/bin'), ('ls','-l','/dev/block/by-name'), ('ls','-l','/dev/block/platform'),
    ('ls','-l','/dev/block/platform/mstar_mci.0/by-name'),
    ('ls','/sys/firmware/devicetree/base'),('ls','/sys/class/graphics'),
    ('dumpsys','SurfaceFlinger'), ('dumpsys','media.codec'), ('dumpsys','media.player'),
    ('dumpsys','display'),('dumpsys','tv_input'),('dumpsys','hdmi_control'))


def collect(adb, serial):
    if not any(d.serial == serial and d.state == 'device' for d in adb.devices()):
        raise RuntimeError('Target is not currently authorized; no reconnect attempted.')
    results = []
    for command in COMMANDS:
        try: results.append({'command':list(command),'output':re.sub(r'(androidboot.serialno=)\S+',r'\1[REDACTED]',adb.shell(serial,*command)),'error':None})
        except Exception as exc: results.append({'command':list(command),'output':None,'error':str(exc)})
    return {'captured_at':datetime.now(timezone.utc).isoformat(),'mode':'read-only','serial':serial,'probes':results}


def save(path, report):
    Path(path).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
