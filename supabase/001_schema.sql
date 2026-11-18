-- 安裝前確認目標專案，請勿在未授權環境執行。資料表預設無匿名存取權。
create table if not exists public.renai_equipment_loans (
  id uuid primary key default gen_random_uuid(),
  request_key uuid not null unique,
  asset_id integer not null check (asset_id > 0),
  borrower text not null check (char_length(trim(borrower)) between 1 and 120),
  unit text not null check (char_length(trim(unit)) between 1 and 120),
  contact text not null check (char_length(trim(contact)) between 1 and 120),
  purpose text not null check (char_length(trim(purpose)) between 1 and 120),
  quantity integer not null check (quantity > 0),
  start_date date not null,
  due_date date not null check (due_date >= start_date),
  status text not null default '待審核' check (status in ('待審核','已核准','借出中','已歸還','已退回')),
  created_at timestamptz not null default now()
);
alter table public.renai_equipment_loans enable row level security;
revoke all on public.renai_equipment_loans from public, anon, authenticated;
grant select, insert on public.renai_equipment_loans to service_role;

-- 每個教具的核准與狀態更新序列化，避免並行核准超額。
create or replace function public.renai_update_loan(p_id uuid, p_target text, p_capacity integer)
returns void language plpgsql security definer set search_path = pg_catalog, public as $$
declare item public.renai_equipment_loans%rowtype; occupied bigint;
begin
 select * into item from public.renai_equipment_loans where id=p_id;
 if not found then raise exception '找不到借用單'; end if;
 perform pg_advisory_xact_lock(188819, item.asset_id);
 select * into item from public.renai_equipment_loans where id=p_id for update;
 if not ((item.status='待審核' and p_target in ('已核准','已退回')) or (item.status='已核准' and p_target in ('借出中','已退回')) or (item.status='借出中' and p_target='已歸還')) then
  raise exception '無法執行此狀態變更';
 end if;
 if p_target='已核准' then
  if p_capacity is null or p_capacity < 1 then raise exception '教具數量無效'; end if;
  select coalesce(sum(quantity),0) into occupied from public.renai_equipment_loans
   where asset_id=item.asset_id and id<>item.id and (status='借出中' or (status='已核准' and start_date<=item.due_date and due_date>=item.start_date));
  if occupied+item.quantity>p_capacity then raise exception '同期間數量不足，請確認借用紀錄'; end if;
 end if;
 update public.renai_equipment_loans set status=p_target where id=p_id;
end $$;
revoke all on function public.renai_update_loan(uuid,text,integer) from public, anon, authenticated;
grant execute on function public.renai_update_loan(uuid,text,integer) to service_role;
