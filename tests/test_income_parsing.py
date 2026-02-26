import asyncio
import logging
import sys
from services.ai_service import AIService

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_income_parsing():
    ai = AIService()
    
    test_cases = [
        "HARI INI DAPAT 100 RB",
        "DAPAT UANG DARI TANTE 200 RB",
        "Gajian bulan ini 5jt", 
        "Dapet transferan 50rb"
    ]
    
    print("\nStarting Income Parsing Test...\n")
    
    for text in test_cases:
        print(f"Input: {text}")
        try:
            results = await ai.parse_expense(text)
            for res in results:
                print(f"  -> Item: {res.get('item')}")
                print(f"  -> Amount: {res.get('amount')}")
                print(f"  -> Category: {res.get('category')}")
                
            if not results:
                print("  -> NO RESULT FROM AI")
                
        except Exception as e:
            print(f"  -> ERROR: {e}")
        print("-" * 30)

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_income_parsing())
