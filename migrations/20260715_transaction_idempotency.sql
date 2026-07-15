alter table public.transactions
    add column if not exists operation_id text;

create unique index if not exists transactions_user_operation_uidx
    on public.transactions (user_id, operation_id)
    where operation_id is not null;

alter table public.income
    add column if not exists operation_id text;

create unique index if not exists income_user_operation_uidx
    on public.income (user_id, operation_id)
    where operation_id is not null;
