import asyncio
import os
import sys
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.ai_service import AIService

async def test_ocr():
    service = AIService()
    image_path = r'C:\Users\ASUS\.gemini\antigravity\brain\44ff2b6e-1d57-4adb-827e-4f05573b477c\sample_receipt_1776167519559.png'
    
    if not os.path.exists(image_path):
        # Look for any .png in the directory if the exact name differs
        dir_path = os.path.dirname(image_path)
        files = [f for f in os.listdir(dir_path) if f.startswith('sample_receipt') and f.endswith('.png')]
        if files:
            image_path = os.path.join(dir_path, files[0])
        else:
            print(f"Error: Image not found at {image_path}")
            return

    with open(image_path, 'rb') as f:
        image_bytes = f.read()
    
    print(f"Testing OCR with image: {image_path}")
    
    try:
        result = await service.parse_receipt_image(image_bytes)
        print("\n--- OCR Results ---")
        print(json.dumps(result, indent=2))
        print("-------------------\n")
    except Exception as e:
        print(f"An error occurred during OCR: {e}")

if __name__ == "__main__":
    asyncio.run(test_ocr())
