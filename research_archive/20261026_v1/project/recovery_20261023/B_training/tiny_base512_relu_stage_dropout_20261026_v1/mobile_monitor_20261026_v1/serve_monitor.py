"""Read-only LAN view of the existing MONITOR.md. Standard library only."""
import argparse
import datetime
import html
import json
import pathlib
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


def render(markdown):
    result, table, code = [], False, False
    for line in markdown.splitlines():
        if line.startswith('```'):
            if table:
                result.append('</tbody></table></div>')
                table = False
            result.append('</pre>' if code else '<pre>')
            code = not code
            continue
        if code:
            result.append(html.escape(line) + '\n')
            continue
        if line.startswith('|') and line.endswith('|'):
            cells = [x.strip() for x in line.strip('|').split('|')]
            if all(set(x) <= set('-: ') for x in cells):
                continue
            if not table:
                result.append('<div class="table"><table><thead><tr>' + ''.join('<th>' + html.escape(x) + '</th>' for x in cells) + '</tr></thead><tbody>')
                table = True
            else:
                result.append('<tr>' + ''.join('<td>' + html.escape(x) + '</td>' for x in cells) + '</tr>')
            continue
        if table:
            result.append('</tbody></table></div>')
            table = False
        if line.startswith('#'):
            level = min(len(line) - len(line.lstrip('#')), 4)
            result.append(f'<h{level}>' + html.escape(line.lstrip('#').strip()) + f'</h{level}>')
        elif line.strip():
            result.append('<p>' + html.escape(line) + '</p>')
    if table:
        result.append('</tbody></table></div>')
    if code:
        result.append('</pre>')
    return ''.join(result)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', required=True)
    parser.add_argument('--port', type=int, default=8768)
    parser.add_argument('--monitor', type=pathlib.Path, required=True)
    args = parser.parse_args()
    package = pathlib.Path(__file__).resolve().parent
    access_path = package / 'ACCESS.json'
    if access_path.exists():
        access = json.loads(access_path.read_text(encoding='utf-8'))
    else:
        access = {'token': secrets.token_urlsafe(24)}
        with access_path.open('x', encoding='utf-8') as f:
            json.dump(access, f)
    route = '/' + access['token'] + '/'

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # Never log the private access URL.

        def do_GET(self):
            if urlsplit(self.path).path != route:
                self.send_error(404)
                return
            try:
                markdown = args.monitor.read_text(encoding='utf-8-sig')
                timestamp = datetime.datetime.fromtimestamp(args.monitor.stat().st_mtime).astimezone()
                stale = datetime.datetime.now().astimezone().timestamp() - timestamp.timestamp() > 60
                note = '來源超過60秒未更新；請確認監控時間與狀態。' if stale else '讀取既有監控表；每15秒自動刷新。寬表可左右滑動。'
                body = ('<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="refresh" content="15"><title>SkinDetect 訓練監控</title><style>'
                        'body{font:16px/1.6 system-ui,sans-serif;background:#f2f5f8;color:#182634;margin:0;padding:16px;max-width:1400px;margin:auto}h1{font-size:1.5rem}h2{font-size:1.2rem;margin-top:28px}.notice{background:#dcebf5;border-radius:10px;padding:12px}.table{overflow:auto;background:white;border-radius:10px;margin:16px 0}table{border-collapse:collapse;font-size:14px;white-space:nowrap;width:100%}th,td{padding:9px 12px;border-bottom:1px solid #e1e6eb;text-align:left}th{background:#e5edf4}pre{overflow:auto;background:#172b3b;color:#f0f4f7;padding:12px;border-radius:8px}p{overflow-wrap:anywhere}'
                        '</style><div class="notice">' + html.escape(note) + '<br>來源檔案時間：' + html.escape(timestamp.strftime('%Y-%m-%d %H:%M:%S %z')) + '</div>' + render(markdown) + '</html>').encode('utf-8')
            except OSError:
                self.send_error(503, 'Monitor temporarily unavailable')
                return
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    import os
    receipt = {'pid': os.getpid(), 'url': f'http://{args.host}:{args.port}{route}', 'monitor': str(args.monitor), 'started_local': datetime.datetime.now().astimezone().isoformat(), 'access_scope': 'same LAN only; no firewall/router/Windows changes', 'refresh_seconds': 15, 'read_only': True}
    receipt_path = package / 'SERVER_RECEIPT.json'
    with receipt_path.open('x', encoding='utf-8') as f:
        json.dump(receipt, f, ensure_ascii=False, indent=2)
    print('Read-only monitor listening', flush=True)
    server.serve_forever(poll_interval=1)


if __name__ == '__main__':
    main()
