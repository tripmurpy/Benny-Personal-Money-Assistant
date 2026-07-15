create table if not exists public.goal_history (
    id bigint generated always as identity primary key,
    goal_id bigint not null references public.goals(id),
    user_id text not null,
    action text not null check (action in ('created', 'contribute', 'withdraw', 'cancelled')),
    amount_delta bigint not null default 0,
    balance_after bigint not null check (balance_after >= 0),
    created_at timestamptz not null default now()
);

create index if not exists goal_history_user_goal_created_idx
    on public.goal_history (user_id, goal_id, created_at desc);

create or replace function public.mutate_goal(
    p_user_id text,
    p_action text,
    p_goal_id bigint default null,
    p_name text default null,
    p_target_amount bigint default null,
    p_deadline date default null,
    p_amount bigint default null
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    v_goal public.goals%rowtype;
    v_delta bigint := 0;
    v_history_action text;
begin
    if nullif(trim(p_user_id), '') is null then
        raise exception 'user_id is required' using errcode = '22023';
    end if;

    if p_action = 'create' then
        if nullif(trim(p_name), '') is null or p_target_amount is null or p_target_amount <= 0 then
            raise exception 'valid name and target are required' using errcode = '22023';
        end if;

        insert into public.goals (user_id, name, target_amount, current_amount, deadline, status)
        values (p_user_id, trim(p_name), p_target_amount, 0, p_deadline, 'active')
        returning * into v_goal;
        v_history_action := 'created';

    elsif p_action = 'cancel' then
        update public.goals
        set status = 'cancelled', updated_at = now()
        where id = p_goal_id and user_id = p_user_id and status <> 'cancelled'
        returning * into v_goal;
        v_history_action := 'cancelled';

    elsif p_action in ('contribute', 'withdraw') then
        if p_amount is null or p_amount <= 0 then
            raise exception 'amount must be positive' using errcode = '22023';
        end if;

        select * into v_goal
        from public.goals
        where id = p_goal_id and user_id = p_user_id and status <> 'cancelled'
        for update;

        if not found then
            raise exception 'goal not found' using errcode = 'P0002';
        end if;

        v_delta := case when p_action = 'contribute' then p_amount else -p_amount end;
        if coalesce(v_goal.current_amount, 0) + v_delta < 0 then
            raise exception 'insufficient goal balance' using errcode = '22003';
        end if;

        update public.goals
        set current_amount = coalesce(current_amount, 0) + v_delta,
            status = case
                when coalesce(current_amount, 0) + v_delta >= target_amount then 'completed'
                else 'active'
            end,
            updated_at = now()
        where id = p_goal_id and user_id = p_user_id
        returning * into v_goal;
        v_history_action := p_action;
    else
        raise exception 'unsupported goal action' using errcode = '22023';
    end if;

    if v_goal.id is null then
        raise exception 'goal not found' using errcode = 'P0002';
    end if;

    insert into public.goal_history (
        goal_id, user_id, action, amount_delta, balance_after
    ) values (
        v_goal.id, p_user_id, v_history_action, v_delta, coalesce(v_goal.current_amount, 0)
    );

    return to_jsonb(v_goal);
end;
$$;

revoke all on table public.goal_history from public, anon, authenticated;
grant select on table public.goal_history to service_role;

revoke all on function public.mutate_goal(text, text, bigint, text, bigint, date, bigint)
    from public, anon, authenticated;
grant execute on function public.mutate_goal(text, text, bigint, text, bigint, date, bigint)
    to service_role;
