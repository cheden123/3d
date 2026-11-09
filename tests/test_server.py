import json,threading,urllib.request,urllib.error
import pytest
from bead_studio.server import Studio

@pytest.fixture
def server():
    with Studio() as s:
        thread=threading.Thread(target=s.serve_forever,daemon=True);thread.start()
        yield s
        s.shutdown();thread.join()

def request(url,data=None,origin=None):
    req=urllib.request.Request(url,data=json.dumps(data).encode() if data is not None else None,
                               headers={'Content-Type':'application/json',**({'Origin':origin} if origin else {})})
    try:
        with urllib.request.urlopen(req) as r:return r.status,r.read(),r.headers
    except urllib.error.HTTPError as e:return e.code,e.read(),e.headers

def test_server_contract_and_access(server):
    s=server
    assert request(s.origin+'/api/health')[0]==404
    assert request(s.url+'api/health')[0]==200
    assert request(s.url+'api/generate',{},'https://other.example')[0]==403
    assert request(s.url+'api/generate',{'diameter':12,'bore':10},s.origin)[0]==400
    status,data,_=request(s.url+'api/generate',{'shape':'D'},s.origin)
    assert status==200
    ident=json.loads(data)['id']
    for name in ['model.stl','model.step','fusion.zip']:
        status,body,headers=request(s.url+f'files/{ident}/{name}')
        assert status==200 and len(body)>100
        assert 'attachment' in headers['Content-Disposition']
    assert request(s.url+'files/notthere/model.stl')[0]==404
    assert request(s.url+'../bead_studio/server.py')[0]==404
    status,cached,_=request(s.url+'api/generate',{'shape':'D'},s.origin)
    assert status==200 and json.loads(cached)['id']==ident
    assert request(s.url+'api/heartbeat',{},s.origin)[0]==200
