begin;

insert into public.user_profiles (user_id, username, first_name)
values ('schema-smoke-user', 'schema_smoke', 'Schema');

insert into public.agent_harness (user_id, preferred_name, roast_intensity)
values ('schema-smoke-user', 'Benny', 3);

insert into public.user_preferences (user_id, preference_key, preference_value)
values ('schema-smoke-user', 'food.favorite', '"bakso"'::jsonb);

insert into public.income (user_id, operation_id, date, time, source, amount)
values ('schema-smoke-user', 'smoke-income:0', current_date, localtime, 'Gaji', 5000000);

with expense as (
    insert into public.transactions
        (user_id, operation_id, date, time, item_name, category, amount)
    values
        ('schema-smoke-user', 'smoke-expense:0', current_date, localtime,
         'Kopi impulsif', 'Food', 35000)
    returning id
)
insert into public.spending_assessments
    (transaction_id, user_id, verdict, reason, confidence)
select id, 'schema-smoke-user', 'unwise', 'Pembelian impulsif', 0.900
from expense;

with session as (
    insert into public.chat_sessions (user_id, telegram_chat_id)
    values ('schema-smoke-user', 'schema-smoke-chat')
    returning id
), message as (
    insert into public.chat_messages
        (session_id, user_id, telegram_message_id, role, content)
    select id, 'schema-smoke-user', 1, 'user', 'Roast pengeluaranku'
    from session
)
insert into public.roast_runs
    (user_id, session_id, period_start, period_end, total_income,
     total_expense, unwise_expense, roast_text, severity)
select 'schema-smoke-user', id, current_date, current_date,
       5000000, 35000, 35000, 'Kopi mahal, tabungan menangis.', 3
from session;

do $$
begin
    if (select count(*) from public.roast_runs where user_id = 'schema-smoke-user') <> 1 then
        raise exception 'Benny schema smoke test failed';
    end if;
end;
$$;

rollback;
