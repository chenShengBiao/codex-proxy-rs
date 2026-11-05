begin;
set local lock_timeout='10s';
lock table _sqlx_migrations in exclusive mode;
do $$
begin
    if not exists (select 1 from _sqlx_migrations where version=202611040038 and success and checksum=decode('316f6a412a03f3a6a8b54cad2dfcc73241d109162d745488971d7d74badb1ce7b2892e6b1970d4f266a66bccc2ea7396','hex')) then
        raise exception 'Unexpected private migration state';
    end if;
    if exists (select 1 from _sqlx_migrations where version=38) then
        if not exists (select 1 from _sqlx_migrations where version=38 and success and checksum=decode('b30bc016cbc15006932140377f50f5b8338fb282aee6776ea63a0c61df1bb50fe0d68077177227d24924f56a6b1afc42','hex')) then
            raise exception 'Unexpected official migration state';
        end if;
        -- 保留升级期间形成的孤立账本，回滚只恢复后续写入的原约束
        alter table client_api_key_budget_windows add constraint client_api_key_budget_windows_client_api_key_id_fkey foreign key (client_api_key_id) references client_api_keys(id) on delete cascade not valid;
        alter table client_api_key_charge_events add constraint client_api_key_charge_events_client_api_key_id_fkey foreign key (client_api_key_id) references client_api_keys(id) on delete cascade not valid;
        delete from _sqlx_migrations where version=38;
    end if;
    update _sqlx_migrations set version=38 where version=202611040038;
end $$;
commit;
