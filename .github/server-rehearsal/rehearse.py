"""一次性隔离数据库演练，不读取生产数据"""
import hashlib,json,os,secrets,shutil,subprocess,tempfile,time
from pathlib import Path
here=Path(__file__).resolve().parent
source=Path(os.environ['SOURCE_DIR']); migrations=source/'backend/migrations'
container='cpr-migration-rehearsal'; password=secrets.token_hex(24)
print('::add-mask::'+password,flush=True)
def run(args,**kwargs):
    return subprocess.run(args,check=True,text=True,**kwargs)
def sql(query,db='rehearsal'):
    return run(['docker','exec','-e','PGPASSWORD='+password,container,'psql','-X','-U','rehearsal','-d',db,'-v','ON_ERROR_STOP=1','-Atc',query],capture_output=True).stdout.strip()
def migrate(path,db='rehearsal',ok=True):
    env={**os.environ,'DATABASE_URL':f'postgres://rehearsal:{password}@127.0.0.1:55432/{db}'}
    result=subprocess.run([str(here/'helper/target/debug/cpr-migration-rehearsal'),str(path)],env=env,text=True,capture_output=True)
    if (result.returncode==0)!=ok:
        raise RuntimeError('Unexpected migrator result: '+result.stderr)
def checksum_rows():
    return dict(line.split('|') for line in sql("select version,encode(checksum,'hex') from _sqlx_migrations where success order by version").splitlines())
def snapshot():
    tables=['provider_accounts','client_api_keys','outbound_proxies','client_api_key_budget_windows','client_api_key_charge_events']
    return {t:sql(f"select coalesce(jsonb_agg(to_jsonb(t) order by to_jsonb(t)::text),'[]'::jsonb) from {t} t") for t in tables}
expected={str(int(p.name.split('_')[0])):hashlib.sha384(p.read_bytes()).hexdigest() for p in migrations.glob('*.sql')}
try:
    run(['docker','run','-d','--name',container,'-p','127.0.0.1:55432:5432','-e','POSTGRES_USER=rehearsal','-e','POSTGRES_DB=rehearsal','-e','POSTGRES_PASSWORD='+password,'postgres:18-bookworm@sha256:bbf83594798e144bff365a9c191c5d779f181fb3135902064ab8ff11918020fc'])
    run(['cargo','build','--manifest-path',str(here/'helper/Cargo.toml')])
    for attempt in range(30):
        try:
            assert sql('select 1')=='1';break
        except Exception:
            time.sleep(1)
    with tempfile.TemporaryDirectory() as temp:
        old=Path(temp)
        for p in migrations.glob('*.sql'):
            if int(p.name.split('_')[0])<38: shutil.copy2(p,old/p.name)
        shutil.copy2(migrations/'202611040038_proxy_direct_fallback.sql',old/'0038_proxy_direct_fallback.sql')
        migrate(old)
        sql("""
        insert into outbound_proxies(id,name,proxy_url,allow_direct_fallback) values ('proxy_true','fixture enabled','http://192.0.2.1:8080',true),('proxy_false','fixture disabled','http://192.0.2.2:8080',false);
        insert into provider_accounts(id,provider_kind,name,authentication_kind,provider_credentials_json,has_refresh_token,credential_observed_at,created_at,updated_at,outbound_proxy_id)
          values ('account_fixture','openai','fixture','api_key','{}',false,now(),now(),now(),'proxy_true');
        insert into client_api_keys(id,name,key,created_at,updated_at) values ('key_fixture','fixture','synthetic-fixture-token',now(),now());
        insert into client_api_key_budget_windows(client_api_key_id,daily_start,daily_end,weekly_start,weekly_end,daily_used_usd,weekly_used_usd)
          values ('key_fixture',now(),now()+interval '1 day',now(),now()+interval '7 days',1.25,2.50);
        insert into client_api_key_charge_events(request_id,client_api_key_id,amount_usd,completed_at) values ('request_fixture','key_fixture',1.25,now());
        """)
        before=snapshot(); original=checksum_rows()
        old_metadata=sql("select (to_jsonb(m)-'version')::text from _sqlx_migrations m where version=38")
        migrate(migrations,ok=False) # 直接升级必须拒绝编号碰撞
        assert snapshot()==before and checksum_rows()==original
        sql((here/'bridge.sql').read_text())
        assert sql("select (to_jsonb(m)-'version')::text from _sqlx_migrations m where version=202611040038")==old_metadata
        migrate(migrations)
        assert checksum_rows()==expected and snapshot()==before
        assert sql("select count(*) from pg_constraint where conname in ('client_api_key_budget_windows_client_api_key_id_fkey','client_api_key_charge_events_client_api_key_id_fkey')")=='0'
        migrate(migrations) # 重启无重复应用
        # 模拟升级后删除凭据：账本保留为合法孤立记录
        sql("delete from client_api_keys where id='key_fixture'")
        assert sql('select count(*) from client_api_key_budget_windows')=='1'
        assert sql('select count(*) from client_api_key_charge_events')=='1'
        after_delete=snapshot()
        sql((here/'rollback.sql').read_text())
        assert checksum_rows()==original and snapshot()==after_delete
        assert sql("select (to_jsonb(m)-'version')::text from _sqlx_migrations m where version=38")==old_metadata
        assert sql("select count(*) from pg_constraint where conname in ('client_api_key_budget_windows_client_api_key_id_fkey','client_api_key_charge_events_client_api_key_id_fkey') and not convalidated")=='2'
        migrate(old)
        sql((here/'bridge.sql').read_text());migrate(migrations)
        assert snapshot()==after_delete and checksum_rows()==expected
        # 官方迁移尚未执行时回滚，也必须安全
        sql((here/'rollback.sql').read_text());sql((here/'bridge.sql').read_text());sql((here/'rollback.sql').read_text())
        assert checksum_rows()==original and snapshot()==after_delete
        migrate(old)
    sql('create database fresh',db='postgres');migrate(migrations,db='fresh')
    assert sql('select count(*) from _sqlx_migrations',db='fresh')=='39'
    print(json.dumps({'verification':'passed','postgres':18,'sqlx':'f1e94ec34dd5f11ad6488a3a8ac7988439a3f757','upgrade':True,'restart':True,'rollback_with_orphan_ledger':True,'reupgrade':True,'fresh_install':True,'proxy_flags_and_account_bindings_preserved':True,'migration_metadata_preserved':True}),flush=True)
finally:
    subprocess.run(['docker','rm','-f',container],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
