import unittest
from types import SimpleNamespace

from services.supabase_service import SupabaseService


class FakeQuery:
    def __init__(self, data):
        self.data = data
        self.filters = []
        self.mode = None
        self.payload = None

    def insert(self, payload):
        self.mode, self.payload = "insert", payload
        return self

    def upsert(self, payload, **_kwargs):
        self.mode, self.payload = "upsert", payload
        return self

    def update(self, payload):
        self.mode, self.payload = "update", payload
        return self

    def delete(self):
        self.mode = "delete"
        return self

    def select(self, _columns):
        self.mode = "select"
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def like(self, key, value):
        self.filters.append((key, value))
        return self

    def limit(self, _value):
        return self

    def execute(self):
        return SimpleNamespace(data=self.data)


class FakeClient:
    def __init__(self, data):
        self.query = FakeQuery(data)

    def table(self, _name):
        return self.query


class LedgerIntegrityTest(unittest.TestCase):
    def service(self, data):
        service = object.__new__(SupabaseService)
        service._client = FakeClient(data)
        return service

    def test_write_requires_database_confirmation_and_is_idempotent(self):
        unconfirmed = self.service([]).add_transactions_bulk(
            "7", [{"item": "Kopi", "amount": 25_000}], "msg-10"
        )
        self.assertFalse(unconfirmed["ok"])

        service = self.service([{"id": 1}])
        confirmed = service.add_transactions_bulk(
            "7", [{"item": "Kopi", "amount": 25_000}], "msg-10"
        )
        self.assertTrue(confirmed["ok"])
        self.assertEqual(service._client.query.mode, "upsert")
        self.assertEqual(service._client.query.payload[0]["operation_id"], "msg-10:0")

    def test_mutations_are_scoped_to_user_and_require_a_changed_row(self):
        service = self.service([{"id": 5}])
        self.assertTrue(service.update_transaction("7", "5", {"amount": 30_000}))
        self.assertEqual(service._client.query.filters, [("user_id", "7"), ("id", "5")])

        missing = self.service([])
        self.assertFalse(missing.delete_transaction("7", "5"))
        self.assertEqual(missing._client.query.filters, [("user_id", "7"), ("id", "5")])

        operation = self.service([{"id": 5}])
        self.assertTrue(operation.delete_operation("7", "transactions", "7:10"))
        self.assertEqual(
            operation._client.query.filters,
            [("user_id", "7"), ("operation_id", "7:10:%")],
        )

        record = self.service([{"id": 5}])
        self.assertEqual(record.get_record("7", "transactions", "5")["id"], 5)
        self.assertEqual(record._client.query.filters, [("user_id", "7"), ("id", "5")])


if __name__ == "__main__":
    unittest.main()
