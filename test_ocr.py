import asyncio
import httpx
from services.ai_service import AIService

async def test_ocr():
    print("Downloading sample receipt image...")
    async with httpx.AsyncClient() as client:
        # Gambar yang Anda lampirkan di chat pertama sebagai contoh
        url = "https://live.staticflickr.com/3851/14825276609_098cac593d_b.jpg"
        response = await client.get(url)
        image_bytes = response.content
    
    print("Image downloaded. Menjalankan AIService.parse_receipt_image()...")
    ai = AIService()
    try:
        res = await ai.parse_receipt_image(image_bytes)
        print("=== Berhasil ===")
        import json
        print(json.dumps(res, indent=2))
    except Exception as e:
        print("Error during OCR:", e)

if __name__ == "__main__":
    asyncio.run(test_ocr())
