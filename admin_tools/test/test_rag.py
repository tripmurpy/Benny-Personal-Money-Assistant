import asyncio
import os
import sys

# Setup relative imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from services.ai_service import AIService

async def test_rag():
    print("Testing RAG Integration...")
    ai = AIService()
    
    # 1. Test a question that requires the RAG Knowledge Base
    # In 'sample_kb.txt' we ingested info mentioning Benny uses /saldo, /setgoal, /setbudget
    query = "Gimana sih cara cek sisa uang aku di aplikasi ini?"
    
    print(f"\nUser: {query}")
    print("AI is thinking (this should trigger a RAG search)...")
    
    response = await ai.chat_with_user(query)
    
    print("\n--- AI Response ---")
    print(response)
    print("-------------------")
    
    # 2. Test a normal friendly chat that shouldn't need RAG
    query2 = "Halo Benny, aku lagi pusing mikirin cicilan nih."
    print(f"\nUser: {query2}")
    response2 = await ai.chat_with_user(query2)
    
    print("\n--- AI Response ---")
    print(response2)
    print("-------------------")

if __name__ == "__main__":
    asyncio.run(test_rag())
