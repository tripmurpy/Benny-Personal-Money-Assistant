import unittest
from copy import deepcopy
from datetime import datetime, timedelta

from services.reminder_service import ReminderService


class FakeDatabase:
    def __init__(self):
        self.context = {"other": "preserved"}

    def get_context(self, _user_id):
        return deepcopy(self.context)

    def set_context(self, _user_id, context):
        self.context = deepcopy(context)
        return True


class ReminderServiceTest(unittest.TestCase):
    def test_preferences_snooze_and_daily_deduplication(self):
        db = FakeDatabase()
        service = ReminderService(db, "7")
        now = datetime(2026, 7, 15, 18, 5)
        inactive = now - timedelta(hours=25)

        self.assertTrue(service.should_send(inactive, now))
        self.assertTrue(service.mark_sent(now))
        self.assertFalse(service.should_send(inactive, now))
        self.assertEqual(db.context["other"], "preserved")

        tomorrow = now + timedelta(days=1)
        self.assertTrue(service.snooze(2, tomorrow))
        self.assertFalse(service.should_send(inactive, tomorrow))


if __name__ == "__main__":
    unittest.main()
