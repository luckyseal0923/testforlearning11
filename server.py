from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from datetime import date
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import json, os, uuid
ROOT = Path(__file__).resolve().parent
CAT = json.loads((ROOT / 'catalog.json').read_text(encoding='utf-8'))
URL = os.environ.get('SUPABASE_URL', '').rstrip('/')
KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
class StoreError(Exception): pass

def supabase(path, method='GET', data=None, prefer=None):
 if not URL or not KEY:
  raise StoreError('尚未設定 SUPABASE_URL 或 SUPABASE_SERVICE_ROLE_KEY')
 parsed=urlparse(URL)
 if parsed.scheme != 'https' or not parsed.hostname or not parsed.hostname.endswith('.supabase.co') or parsed.path not in ('', '/') or parsed.query or parsed.fragment:
  raise StoreError('Supabase 網址格式不正確')
 headers={'apikey':KEY,'Authorization':'Bearer '+KEY,'Accept':'application/json'}
 payload=None
 if data is not None:
  payload=json.dumps(data,ensure_ascii=False).encode('utf-8');headers['Content-Type']='application/json'
 if prefer: headers['Prefer']=prefer
 req=Request(URL+'/rest/v1/'+path,data=payload,headers=headers,method=method)
 try:
  with urlopen(req,timeout=20) as r:
   body=r.read();return json.loads(body) if body else None
 except (HTTPError,URLError,TimeoutError,ValueError):
  raise StoreError('Supabase 連線或資料操作失敗，請檢查後端設定與資料表') from None

def loans():
 rows=supabase('renai_equipment_loans?select=id,asset_id,borrower,unit,contact,purpose,quantity,start_date,due_date,status,created_at&order=created_at.desc')
 return [{**r,'start':r['start_date'],'due':r['due_date']} for r in rows]

class Handler(BaseHTTPRequestHandler):
 def response(self,status,data,content='application/json; charset=utf-8'):
  b=data if isinstance(data,bytes) else json.dumps(data,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type',content);self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  path=urlparse(self.path).path
  if path=='/': return self.response(200,(ROOT/'index.html').read_bytes(),'text/html; charset=utf-8')
  if path.startswith('/photos/'):
   filename=path.removeprefix('/photos/')
   if len(filename)==6 and filename[:2].isdigit() and filename.endswith('.png') and 1<=int(filename[:2])<=36:
    photo=ROOT/'photos'/filename
    if photo.is_file():return self.response(200,photo.read_bytes(),'image/png')
   return self.response(404,{'error':'找不到照片'})
  if path=='/api/catalog':return self.response(200,CAT)
  if path=='/api/loans':
   try:return self.response(200,loans())
   except StoreError as e:return self.response(503,{'error':str(e)})
  return self.response(404,{'error':'找不到頁面'})
 def do_POST(self):
  try:
   if self.headers.get('Origin') not in ('http://127.0.0.1:8768','http://localhost:8768'):raise ValueError('來源不符')
   length=int(self.headers.get('Content-Length','0'))
   if length<=0 or length>8192:raise ValueError('資料格式錯誤')
   x=json.loads(self.rfile.read(length));path=urlparse(self.path).path
   if path=='/api/submit':
    asset=next((a for a in CAT if a['id']==int(x['asset_id'])),None)
    if not asset:raise ValueError('教具不存在')
    for k in ['borrower','unit','contact','purpose']:
     if not isinstance(x.get(k),str) or not 0<len(x[k].strip())<=120:raise ValueError('請完整填寫資料（每欄最多 120 字）')
    qty=int(x['quantity']);start=date.fromisoformat(x['start']);due=date.fromisoformat(x['due'])
    request_key=str(uuid.UUID(x['request_key']))
    if qty<1 or qty>asset['quantity'] or due<start:raise ValueError('數量或日期不正確')
    data={'request_key':request_key,'asset_id':asset['id'],'borrower':x['borrower'].strip(),'unit':x['unit'].strip(),'contact':x['contact'].strip(),'purpose':x['purpose'].strip(),'quantity':qty,'start_date':start.isoformat(),'due_date':due.isoformat()}
    rows=supabase('renai_equipment_loans?on_conflict=request_key','POST',data,'resolution=ignore-duplicates,return=representation')
    if not rows:
     rows=supabase('renai_equipment_loans?request_key=eq.'+request_key+'&select=id,request_key,asset_id,borrower,unit,contact,purpose,quantity,start_date,due_date')
     if len(rows)!=1 or any(rows[0].get(k)!=v for k,v in data.items()):raise ValueError('此申請編號已使用，內容不同；請重新填寫')
    return self.response(200,{'id':rows[0]['id']})
   if path=='/api/status':
    loan_id=str(uuid.UUID(x['id']));rows=supabase('renai_equipment_loans?id=eq.'+loan_id+'&select=id,asset_id')
    if not rows:raise ValueError('找不到借用單')
    asset=next((a for a in CAT if a['id']==rows[0]['asset_id']),None)
    if not asset:raise ValueError('教具不存在於清單')
    if x.get('status') not in ('已核准','已退回','借出中','已歸還'):raise ValueError('狀態不正確')
    supabase('rpc/renai_update_loan','POST',{'p_id':loan_id,'p_target':x['status'],'p_capacity':asset['quantity']})
    return self.response(200,{'ok':True})
   return self.response(404,{'error':'找不到操作'})
  except (ValueError,KeyError,TypeError,json.JSONDecodeError) as e:return self.response(400,{'error':str(e)})
  except StoreError as e:return self.response(503,{'error':str(e)})
  except Exception:return self.response(500,{'error':'處理失敗，請稍後再試'})
if __name__=='__main__':
 print('教具借用試用版：http://127.0.0.1:8768/（僅本機）',flush=True)
 ThreadingHTTPServer(('127.0.0.1',8768),Handler).serve_forever()
