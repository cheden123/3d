"""Loopback-only application server. CAD operations are serialized."""
import argparse
from collections import OrderedDict
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import io,json,mimetypes,secrets,sys,tempfile,threading,time,webbrowser,zipfile,logging
from urllib.parse import urlsplit
from .cad import Settings, UserError, NAMES, build, metrics, export

BASE=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))
log=logging.getLogger('bead_studio')

def fusion_archive(settings):
    memory=io.BytesIO()
    with zipfile.ZipFile(memory,'w',zipfile.ZIP_DEFLATED) as z:
        for name in ['Paracord550.py','Paracord550.manifest']:
            z.write(BASE/'fusion_template'/name,'Paracord550/'+name)
        z.write(BASE/'bead_studio'/'model_spec.py','Paracord550/model_spec.py')
        z.writestr('Paracord550/selection.json',json.dumps({'shape':settings.shape,'values':settings.parameters()}))
        z.writestr('settings.bead.json',json.dumps({'version':1,'settings':asdict(settings)},ensure_ascii=False,indent=2))
        z.writestr('START_HERE.txt',
                  'Fusion: Utilities > Scripts and Add-Ins (Shift+S) > Scripts > +.\n'
                  'Add the Paracord550 folder, then Run. No external Python is required.\n'
                  'Modify > Change Parameters edits dimensions. F3D is saved to fusion_exports.\n'
                  'This is an editable script project, not a pre-built F3D.\n')
    return memory.getvalue()

class Studio(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,port=0):
        self.token=secrets.token_urlsafe(24)
        self.tmp=tempfile.TemporaryDirectory(prefix='bead-studio-')
        self.cache=OrderedDict(); self.lock=threading.Lock(); self.last_seen=time.monotonic()
        super().__init__(('127.0.0.1',port),Handler)
        self.origin=f'http://127.0.0.1:{self.server_port}'
        self.prefix='/'+self.token+'/'
        self.url=self.origin+self.prefix

    def server_close(self):
        super().server_close()
        self.tmp.cleanup()

    def generate(self,settings):
        key=json.dumps(asdict(settings),sort_keys=True)
        with self.lock:
            for ident,item in self.cache.items():
                if item['key']==key:
                    self.cache.move_to_end(ident)
                    return item['response']
            body=build(settings)
            ident=secrets.token_hex(12)
            base=Path(self.tmp.name)/ident
            export(body,base.with_suffix('.stl'),base.with_suffix('.step'))
            result={'id':ident,'name':NAMES[settings.shape],'settings':asdict(settings),
                    'wall':round(settings.minimum_wall,2),**metrics(body)}
            self.cache[ident]={'key':key,'response':result,'settings':settings,'base':base}
            while len(self.cache)>12:
                _,old=self.cache.popitem(last=False)
                old['base'].with_suffix('.stl').unlink(missing_ok=True)
                old['base'].with_suffix('.step').unlink(missing_ok=True)
            return result

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass

    def send(self,status,data,content_type='application/json; charset=utf-8',filename=None):
        if not isinstance(data,bytes):
            data=json.dumps(data,ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'")
        if filename:
            self.send_header('Content-Disposition',f'attachment; filename="{filename}"')
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError,ConnectionResetError):
            pass

    def route(self):
        s=self.server
        if self.headers.get('Host')!=f'127.0.0.1:{s.server_port}':
            self.send(403,{'error':'Адрес недоступен.'}); return None
        path=urlsplit(self.path).path
        if not path.startswith(s.prefix):
            self.send(404,{'error':'Откройте программу через ярлык.'}); return None
        return path[len(s.prefix):]

    def do_GET(self):
        path=self.route()
        if path is None:return
        if path=='api/health':
            self.send(200,{'ok':True,'version':'1.0.0'}); return
        if path.startswith('files/'):
            parts=path.split('/')
            if len(parts)!=3 or parts[2] not in ['model.stl','model.step','fusion.zip']:
                self.send(404,{'error':'Файл не найден.'}); return
            with self.server.lock:
                item=self.server.cache.get(parts[1])
                if not item:
                    self.send(404,{'error':'Модель устарела. Нажмите «Обновить модель».'}); return
                kind=parts[2]
                if kind=='fusion.zip':
                    data=fusion_archive(item['settings']); content='application/zip'
                else:
                    data=item['base'].with_suffix('.'+kind.split('.')[-1]).read_bytes()
                    content='model/stl' if kind=='model.stl' else 'application/step'
                filename='Bead_'+item['settings'].shape+'.'+('zip' if kind=='fusion.zip' else kind.split('.')[-1])
            self.send(200,data,content,filename); return
        if not path:path='index.html'
        file=(BASE/'web'/path).resolve()
        if not file.is_relative_to((BASE/'web').resolve()) or not file.is_file():
            self.send(404,{'error':'Файл не найден.'});return
        content='text/javascript' if file.suffix=='.js' else mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
        self.send(200,file.read_bytes(),content)

    def do_POST(self):
        path=self.route()
        if path is None:return
        if self.headers.get('Origin')!=self.server.origin:
            self.send(403,{'error':'Запрос недоступен.'});return
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=8192:
                self.send(413,{'error':'Слишком большой запрос.'});return
            data=json.loads(self.rfile.read(length))
            if path=='api/heartbeat':
                self.server.last_seen=time.monotonic();self.send(200,{'ok':True});return
            if path=='api/stop':
                self.send(200,{'ok':True}); threading.Thread(target=self.server.shutdown,daemon=True).start();return
            if path!='api/generate':
                self.send(404,{'error':'Команда не найдена.'});return
            settings=Settings.read(data)
            self.server.last_seen=time.monotonic()
            self.send(200,self.server.generate(settings))
        except (UserError,json.JSONDecodeError,ValueError) as error:
            self.send(400,{'error':str(error) if isinstance(error,UserError) else 'Не удалось прочитать настройки.'})
        except Exception:
            log.exception('CAD operation failed')
            self.send(500,{'error':'Не удалось создать модель. Уменьшите отверстие или верните исходные настройки.'})

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--no-browser',action='store_true')
    parser.add_argument('--port',type=int,default=0)
    parser.add_argument('--status-file',type=Path,help=argparse.SUPPRESS)
    args=parser.parse_args()
    logdir=Path.home()/'AppData'/'Local'/'BeadStudio' if sys.platform=='win32' else Path.home()/'.local/state/bead-studio'
    logdir.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(filename=logdir/'app.log',level=logging.INFO,encoding='utf-8')
    with Studio(args.port) as server:
        if args.status_file:args.status_file.write_text(server.url,encoding='utf-8')
        if not args.no_browser:webbrowser.open(server.url)
        if sys.stdout:print(server.url,flush=True)
        def idle_stop():
            while True:
                time.sleep(15)
                if time.monotonic()-server.last_seen>300:
                    server.shutdown();return
        threading.Thread(target=idle_stop,daemon=True).start()
        server.serve_forever(poll_interval=.3)

if __name__=='__main__':main()
