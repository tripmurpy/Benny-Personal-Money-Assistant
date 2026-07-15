from pathlib import Path

from services.goals_service import GoalsService


class FakeDatabase:
    def __init__(self):
        self.goals = []
        self.history = []
        self.next_id = 1

    def create_goal(self, user_id, name, target, deadline=None):
        goal = {
            "id": self.next_id,
            "user_id": user_id,
            "name": name,
            "target_amount": target,
            "current_amount": 0,
            "status": "active",
        }
        self.next_id += 1
        self.goals.append(goal)
        self.history.append(self._entry(goal, "created", 0))
        return True

    def get_goals(self, user_id):
        return [
            goal.copy()
            for goal in self.goals
            if goal["user_id"] == user_id and goal["status"] != "cancelled"
        ]

    def _mutate(self, user_id, goal_id, delta, action):
        goal = next(
            (
                goal
                for goal in self.goals
                if goal["id"] == goal_id and goal["user_id"] == user_id
            ),
            None,
        )
        if not goal or goal["current_amount"] + delta < 0:
            return None
        goal["current_amount"] += delta
        goal["status"] = (
            "completed"
            if goal["current_amount"] >= goal["target_amount"]
            else "active"
        )
        self.history.append(self._entry(goal, action, delta))
        return goal.copy()

    def contribute_goal(self, user_id, goal_id, amount):
        return self._mutate(user_id, goal_id, amount, "contribute")

    def withdraw_goal(self, user_id, goal_id, amount):
        return self._mutate(user_id, goal_id, -amount, "withdraw")

    def get_goal_history(self, user_id, goal_id, limit=20):
        return [
            row.copy()
            for row in reversed(self.history)
            if row["user_id"] == user_id and row["goal_id"] == goal_id
        ][:limit]

    def delete_goal(self, user_id, goal_id):
        goal = next(
            (
                goal
                for goal in self.goals
                if goal["id"] == goal_id and goal["user_id"] == user_id
            ),
            None,
        )
        if not goal:
            return False
        goal["status"] = "cancelled"
        self.history.append(self._entry(goal, "cancelled", 0))
        return True

    @staticmethod
    def _entry(goal, action, delta):
        return {
            "goal_id": goal["id"],
            "user_id": goal["user_id"],
            "action": action,
            "amount_delta": delta,
            "balance_after": goal["current_amount"],
        }


def verify_goal_logic():
    db = FakeDatabase()
    goals = GoalsService(db=db, user_id="owner")
    stranger = GoalsService(db=db, user_id="stranger")

    assert goals.set_goal("Liburan", 1_000)
    assert not goals.set_goal("liburan", 1_000)
    assert stranger.get_goals() == []
    assert goals.contribute("Liburan", 400)["current_amount"] == 400
    assert goals.withdraw("Liburan", 401) is None
    assert goals.get_goals()[0]["current_amount"] == 400
    assert goals.withdraw("Liburan", 100)["current_amount"] == 300
    completed = goals.contribute("Liburan", 700)
    assert completed["current_amount"] == 1_000
    assert completed["status"] == "completed"
    assert [row["action"] for row in goals.get_history("Liburan")] == [
        "contribute",
        "withdraw",
        "contribute",
        "created",
    ]

    migration = Path(__file__).parents[1] / "migrations" / "20260715_actionable_goals.sql"
    sql = migration.read_text(encoding="utf-8").lower()
    assert "for update" in sql and "insert into public.goal_history" in sql
    assert sql.index("insert into public.goal_history") < sql.index("return to_jsonb(v_goal)")


if __name__ == "__main__":
    verify_goal_logic()
    print("Goal verification passed")
