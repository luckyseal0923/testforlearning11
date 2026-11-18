# 教具借用網站（Supabase 本機試用）

網站程式以 Python 3 在 `127.0.0.1:8768` 執行，借用資料預計存放 Supabase。此版無登入或管理員權限，僅限個人電腦測試，**不可開放網路或使用真實個資**。ChatGPT Site 仍須另行改造及部署，不能直接執行此 Python 程式。

## 設定

1. 在指定 Supabase 專案檢查是否有同名資料表或函式，確認後由有權限者執行 `supabase/001_schema.sql`。SQL 未自動執行；`IF NOT EXISTS` 不會修正已存在但結構不同的資料表。
2. 執行前於安全的本機環境變數設定 `SUPABASE_URL` 與 `SUPABASE_SERVICE_ROLE_KEY`。根目錄現有 publishable key 不是 service role key，不能取代後者。**不可將 service role key 貼到網頁、GitHub 或聊天中**。
3. 執行 `python server.py`，開啟 http://127.0.0.1:8768/。GitHub 的 `catalog.json` 僅包含示範資料與無實際照片，原本的本機檔案保留不變。
4. 完成權限與資料表設定後，以合成資料測試送單、重試、核准、借出及歸還；現有本機 SQLite 借用資料不會自動遷移。

資料表啟用 RLS，匿名及一般使用者不可直接讀寫。後端使用 service role 讀寫並僅監聽本機，絕不可將該金鑰提供給瀏覽器或將此服務直接公開。庫存核准使用資料庫鎖並保守計算借出中的物品；實際數量需先盤點。正式上線仍需登入、角色權限、稽核、備份及完整流程驗收。
