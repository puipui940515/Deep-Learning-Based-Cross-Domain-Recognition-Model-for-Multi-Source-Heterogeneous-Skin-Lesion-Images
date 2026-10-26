"""Keep one existing monitor tunnel active; never restart SSH or training."""
import ctypes
import datetime
import json
import pathlib
import sys
import time
import urllib.request
from ctypes import wintypes

package = pathlib.Path(__file__).resolve().parent
receipt = json.loads((package / 'TUNNEL_REPAIR1.json').read_text(encoding='utf-8-sig'))
kernel = ctypes.WinDLL('kernel32', use_last_error=True)
kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel.OpenProcess.restype = wintypes.HANDLE
kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
kernel.CloseHandle.argtypes = [wintypes.HANDLE]
handle = kernel.OpenProcess(0x1000, False, receipt['pid'])
if not handle:
    sys.exit('Tunnel process unavailable; no restart attempted.')
try:
    with (package / 'tunnel_repair1_health.jsonl').open('x', encoding='utf-8') as log:
        while True:
            code = wintypes.DWORD()
            if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value != 259:
                log.write(json.dumps({'at': datetime.datetime.now().astimezone().isoformat(), 'status': 'tunnel_exited_no_restart'}) + '\n')
                log.flush()
                break
            event = {'at': datetime.datetime.now().astimezone().isoformat()}
            try:
                with urllib.request.urlopen(receipt['url'], timeout=15) as response:
                    body = response.read(200000).decode('utf-8')
                    if response.status != 200 or 'Tiny／Base512' not in body:
                        raise RuntimeError('Unexpected monitor response')
                event['status'] = 'monitor_reachable'
            except Exception as error:
                event.update(status='health_failed_no_restart', error=str(error))
                log.write(json.dumps(event, ensure_ascii=False) + '\n')
                log.flush()
                break
            log.write(json.dumps(event, ensure_ascii=False) + '\n')
            log.flush()
            time.sleep(60)
finally:
    kernel.CloseHandle(handle)
