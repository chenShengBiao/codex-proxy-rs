alter table outbound_proxies
    add column allow_direct_fallback boolean not null default false;
