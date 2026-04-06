import os
import sys
import json
import logging
import argparse
from typing import List
import requests

# Set up relative imports to reuse bot's config and services
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config import Config
from services.supabase_service import SupabaseService

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    import fitz  # PyMuPDF
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    print("Please install required packages: pip install PyMuPDF langchain-text-splitters requests")
    sys.exit(1)

# HuggingFace Settings
# We use the free interference API. Recommended model: all-MiniLM-L6-v2 (fast, 384 dims, good for standard retrieval)
HF_API_URL = "https://router.huggingface.co/hf-inference/models/BAAI/bge-small-en-v1.5"
# HF_API_URL_OLD = "https://api-inference.huggingface.co/models/sentence-transformers/all-MiniLM-L6-v2" (Deprecated - 410 Gone)
HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HUGGINGFACE_API_KEY")  # Check both names


class DataIngestor:
    def __init__(self):
        Config.validate()
        self.db = SupabaseService()

        if not HF_TOKEN:
            logger.warning("HUGGINGFACE_TOKEN not found in environment variables. Depending on HF rate limits, you might get blocked soon.")

        self.headers = {"Authorization": f"Bearer {HF_TOKEN}"} if HF_TOKEN else {}

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )

    def extract_text_from_pdf(self, file_path: str) -> str:
        """Extracts all text from a PDF file using PyMuPDF."""
        logger.info(f"Extracting text from {file_path}...")
        text = ""
        try:
            doc = fitz.open(file_path)
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text += page.get_text() + "\n"
            return text
        except Exception as e:
            logger.error(f"Error reading PDF {file_path}: {e}")
            return ""

    def extract_text_from_txt(self, file_path: str) -> str:
        """Extracts text from a standard txt or md file."""
        logger.info(f"Extracting text from {file_path}...")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading TXT {file_path}: {e}")
            return ""

    def extract_text_from_json(self, file_path: str) -> str:
        """Extracts text from a JSON file by converting structured data to readable text."""
        logger.info(f"Extracting text from JSON {file_path}...")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Handle array of menu items (e.g., [{name, description, price}, ...])
            if isinstance(data, list):
                parts = []
                for item in data:
                    if isinstance(item, dict):
                        name = item.get('name', '')
                        desc = item.get('description', '')
                        price = item.get('price', '')
                        line = f"{name}: {desc}" if desc else name
                        if price:
                            line += f" - Harga: Rp {price}"
                        parts.append(line)
                    else:
                        parts.append(str(item))
                return "\n".join(parts)
            elif isinstance(data, dict):
                return json.dumps(data, indent=2, ensure_ascii=False)
            else:
                return str(data)
        except Exception as e:
            logger.error(f"Error reading JSON {file_path}: {e}")
            return ""

    def chunk_text(self, text: str) -> List[str]:
        """Splits large text into smaller chunks suitable for embedding."""
        logger.info("Chunking text...")
        chunks = self.text_splitter.split_text(text)
        logger.info(f"Created {len(chunks)} chunks.")
        return chunks

    def get_embedding(self, text: str) -> List[float]:
        """Gets vector embedding from HuggingFace API."""
        try:
            response = requests.post(
                HF_API_URL,
                headers=self.headers,
                json={"inputs": text, "options": {"wait_for_model": True}}
            )
            response.raise_for_status()

            # The API returns a list of lists (one list of floats per input string)
            # Since we only send one input string, we want the first list.
            # Some HF models return 1D array immediately if inputs is a single string not in a list,
            # but we explicitly passed it in a list `["text"]` above.
            result = response.json()

            if isinstance(result, list) and len(result) > 0 and isinstance(result[0], list):
                return result[0]  # Return the actual 384 dim vector
            elif isinstance(result, list) and len(result) > 0 and isinstance(result[0], float):
                return result  # Occurs with some specific pipeline endpoints

            logger.error(f"Unexpected HF API response format. Check token or model. Response: {result[:50]}...")
            return []

        except requests.exceptions.RequestException as e:
            logger.error(f"HuggingFace API Request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response Content: {e.response.text}")
            return []

    def ingest_file(self, file_path: str, source_name: str | None = None):
        """Main pipeline: Read -> Chunk -> Embed -> Save to Supabase."""
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return

        if source_name is None:
            source_name = os.path.basename(file_path)

        # 1. Extract Text
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.pdf':
            text = self.extract_text_from_pdf(file_path)
        elif ext in ['.txt', '.md', '.csv']:
            text = self.extract_text_from_txt(file_path)
        elif ext == '.json':
            text = self.extract_text_from_json(file_path)
        else:
            logger.error(f"Unsupported file extension: {ext}")
            return

        if not text.strip():
            logger.warning("No text extracted. Skipping.")
            return

        # 2. Chunk Text
        chunks = self.chunk_text(text)

        # 3 & 4. Embed and Save
        logger.info("Generating embeddings and saving to Supabase...")
        success_count = 0

        for i, chunk in enumerate(chunks):
            embedding = self.get_embedding(chunk)

            if not embedding:
                logger.error(f"Skipping chunk {i} due to embedding failure.")
                continue

            # Prepare data for Supabase
            data = {
                "content": chunk,
                "metadata": {
                    "source": source_name,
                    "chunk_index": i,
                    "total_chunks": len(chunks)
                },
                "embedding": embedding
            }

            try:
                # Insert into kb_documents table
                self.db.client.table('kb_documents').insert(data).execute()
                success_count += 1
                if i % 10 == 0:
                    logger.info(f"Processed {i}/{len(chunks)} chunks...")
            except Exception as e:
                logger.error(f"Failed to insert chunk {i} into Supabase: {e}")

        logger.info(f"Ingestion complete! Successfully saved {success_count}/{len(chunks)} chunks from {source_name}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest documents into Supabase for RAG.")
    parser.add_argument("file_path", help="Path to the PDF, Markdown, or TXT file to ingest.")
    parser.add_argument("--source", help="Optional source name tag (defaults to filename).", default=None)

    args = parser.parse_args()

    ingestor = DataIngestor()
    ingestor.ingest_file(args.file_path, args.source)
