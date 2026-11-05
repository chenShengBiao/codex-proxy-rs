begin;
set local lock_timeout='10s';
lock table _sqlx_migrations in exclusive mode;
do $$
begin
    if not exists (select 1 from _sqlx_migrations where version=38 and success and checksum=decode('316f6a412a03f3a6a8b54cad2dfcc73241d109162d745488971d7d74badb1ce7b2892e6b1970d4f266a66bccc2ea7396','hex'))
       or exists (select 1 from _sqlx_migrations where version=202611040038)
       or not exists (select 1 from information_schema.columns where table_schema=current_schema() and table_name='outbound_proxies' and column_name='allow_direct_fallback') then
        raise exception 'Unexpected custom migration state';
    end if;
    update _sqlx_migrations set version=202611040038 where version=38;
end $$;
commit;
