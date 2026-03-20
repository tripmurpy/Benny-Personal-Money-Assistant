import asyncio
import os
from datetime import datetime

os.environ["GROQ_API_KEY"] = "gsk_..." # Wait, it uses config
from config import Config
from services.expense_query_service import get_expense_query_service
from services.ai_service import AIService

async def test_detect():
    eqs = get_expense_query_service()
    res = eqs.detect("kemarin jam 12 aku beli apa ya")
    print("Test 1:", res)
    
    res = eqs.detect("jam 12 siang jajan apa aja")
    print("Test 2:", res)

    print("---")
    ais = AIService()
    txs = [
        {"item_name": "Kopi Susu", "category": "Drink", "amount": 25000, "date": "2026-03-08", "time": "12:05"},
        {"item_name": "Nasi Goreng", "category": "Food", "amount": 50000, "date": "2026-03-08", "time": "12:30"}
    ]
    txt = await ais.summarize_expenses(txs, "Hari Ini", "jam 12 siang jajan apa aja")
    print("AI Reply:", txt)

if __name__ == "__main__":
    asyncio.run(test_detect())
