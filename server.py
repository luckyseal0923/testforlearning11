from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from datetime import date
import sqlite3, json, uuid
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parent
DB=ROOT/'loans.sqlite3'
CAT=json.loads((ROOT/'catalog.json').read_text(encoding='utf-8'))
def connect():
 c=sqlite3.connect(DB,timeout=10); c.row_factory=sqlite3.Row; return c
with connect() as c:
 c.execute('CREATE TABLE IF NOT EXISTS loans (id TEXT PRIMARY KEY, asset_id INTEGER NOT NULL, borrower TEXT NOT NULL, unit TEXT NOT NULL, contact TEXT NOT NULL, purpose TEXT NOT NULL, quantity INTEGER NOT NULL, start TEXT NOT NULL, due TEXT NOT NULL, status TEXT NOT NULL, created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
class Handler(BaseHTTPRequestHandler):
 def response(self,status,data,content='application/json; charset=utf-8'):
  b=data if isinstance(data,bytes) else json.dumps(data,ensure_ascii=False).encode(); self.send_response(status); self.send_header('Content-Type',content); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
 def do_GET(self):
  path=urlparse(self.path).path
  if path=='/': return self.response(200,(ROOT/'index.html').read_bytes(),'text/html; charset=utf-8')
  if path.startswith('/photos/'):
   filename=path.removeprefix('/photos/')
   if len(filename)==6 and filename[:2].isdigit() and filename.endswith('.png') and 1<=int(filename[:2])<=36:
    photo=ROOT/'photos'/filename
    if photo.is_file(): return self.response(200,photo.read_bytes(),'image/png')
   return self.response(404,{'error':'找不到照片'})
  if path=='/api/catalog': return self.response(200,CAT)
  if path=='/api/loans':
   with connect() as c: rows=[dict(r) for r in c.execute('SELECT * FROM loans ORDER BY created DESC')]
   return self.response(200,rows)
  return self.response(404,{'error':'找不到頁面'})
 def do_POST(self):
  try:
   if self.headers.get('Origin') not in ('http://127.0.0.1:8768','http://localhost:8768'): raise ValueError('來源不符')
   length=int(self.headers.get('Content-Length','0'))
   if length<=0 or length>8192: raise ValueError('資料格式錯誤')
   x=json.loads(self.rfile.read(length)); path=urlparse(self.path).path
   with connect() as c:
    c.execute('BEGIN IMMEDIATE')
    if path=='/api/submit':
     asset=next((a for a in CAT if a['id']==int(x['asset_id'])),None)
     if not asset: raise ValueError('教具不存在')
     for k in ['borrower','unit','contact','purpose']:
      if not isinstance(x.get(k),str) or not 0<len(x[k].strip())<=120: raise ValueError('請完整填寫資料（每欄最多 120 字）')
     qty=int(x['quantity']); start=date.fromisoformat(x['start']); due=date.fromisoformat(x['due'])
     if qty<1 or qty>asset['quantity'] or due<start: raise ValueError('數量或日期不正確')
     id=str(uuid.uuid4()); c.execute('INSERT INTO loans(id,asset_id,borrower,unit,contact,purpose,quantity,start,due,status) VALUES (?,?,?,?,?,?,?,?,?,?)',(id,asset['id'],x['borrower'].strip(),x['unit'].strip(),x['contact'].strip(),x['purpose'].strip(),qty,start.isoformat(),due.isoformat(),'待審核'))
     c.commit(); return self.response(200,{'id':id})
    if path=='/api/status':
     row=c.execute('SELECT * FROM loans WHERE id=?',(x.get('id'),)).fetchone()
     if not row: raise ValueError('找不到借用單')
     target=x.get('status'); transitions={'待審核':['已核准','已退回'],'已核准':['借出中','已退回'],'借出中':['已歸還']}
     if target not in transitions.get(row['status'],[]): raise ValueError('無法執行此狀態變更')
     if target=='已核准':
      asset=next(a for a in CAT if a['id']==row['asset_id'])
      used=c.execute("SELECT COALESCE(SUM(quantity),0) FROM loans WHERE asset_id=? AND status IN ('已核准','借出中') AND start<=? AND due>=?",(row['asset_id'],row['due'],row['start'])).fetchone()[0]
      if used+row['quantity']>asset['quantity']: raise ValueError('同期間數量不足，請確認借用紀錄')
     c.execute('UPDATE loans SET status=? WHERE id=?',(target,row['id'])); c.commit(); return self.response(200,{'ok':True})
   return self.response(404,{'error':'找不到操作'})
  except (ValueError,KeyError,TypeError,json.JSONDecodeError) as e: return self.response(400,{'error':str(e)})
  except Exception: return self.response(500,{'error':'儲存失敗，請稍後再試'})
if __name__=='__main__':
 print('教具借用試用版：http://127.0.0.1:8768/（僅本機）',flush=True)
 ThreadingHTTPServer(('127.0.0.1',8768),Handler).serve_forever()
