"""
Google Sheets Service - Clean & Optimized
Handles all Google Sheets operations with caching and dynamic sheet access.
"""

import gspread
from google.oauth2.service_account import Credentials
from config import Config
import re
import time
import json
import os
from typing import List, Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)


class SheetsService:
    """Optimized Google Sheets service with caching and dynamic sheet access."""
    
    _instance = None
    _cache = {}
    _cache_ttl = 60  # Cache for 60 seconds
    _last_cache_time = {}
    
    def __new__(cls):
        """Singleton pattern for connection reuse."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize Google Sheets connection with retry logic."""
        if self._initialized:
            return
            
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        # Load credentials from env or file
        json_creds = os.getenv("GOOGLE_CREDENTIALS_JSON")
        creds = (
            Credentials.from_service_account_info(json.loads(json_creds), scopes=scopes)
            if json_creds
            else Credentials.from_service_account_file(Config.GOOGLE_CREDS_PATH, scopes=scopes)
        )
        
        self.client = gspread.authorize(creds)
        self._connect_with_retry()
        self._initialized = True
    
    def _connect_with_retry(self, max_retries: int = 3):
        """Connect to spreadsheet with retry logic."""
        for attempt in range(max_retries):
            try:
                self.spreadsheet = self.client.open_by_key(Config.SPREADSHEET_ID)
                self.sheet = self.spreadsheet.sheet1  # Default sheet for transactions
                logger.info("✅ Google Sheets connected")
                return
            except Exception as e:
                logger.warning(f"Connection attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    logger.error("❌ Connection failed after retries")
                    raise
    
    def get_worksheet(self, sheet_name: str):
        """
        Get worksheet by name with caching.
        
        Args:
            sheet_name: Name of the worksheet
            
        Returns:
            Worksheet object
        """
        cache_key = f"worksheet_{sheet_name}"
        
        # Check cache
        if cache_key in self._cache:
            cached_time = self._last_cache_time.get(cache_key, 0)
            if time.time() - cached_time < self._cache_ttl:
                return self._cache[cache_key]
        
        # Fetch and cache
        try:
            worksheet = self.spreadsheet.worksheet(sheet_name)
            self._cache[cache_key] = worksheet
            self._last_cache_time[cache_key] = time.time()
            return worksheet
        except gspread.WorksheetNotFound:
            logger.warning(f"Worksheet '{sheet_name}' not found")
            return None
    
    def create_worksheet(self, sheet_name: str, headers: Optional[List[str]] = None):
        """
        Create new worksheet with optional headers.
        Safe: returns existing sheet if it already exists.
        """
        try:
            # Check if already exists first
            existing = self.spreadsheet.worksheet(sheet_name)
            logger.info(f"Sheet '{sheet_name}' already exists, skipping creation")
            return existing
        except gspread.WorksheetNotFound:
            pass
        
        try:
            worksheet = self.spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=20)
            if headers:
                worksheet.append_row(headers)
            logger.info(f"✅ Created worksheet: {sheet_name}")
            return worksheet
        except Exception as e:
            logger.error(f"Failed to create worksheet: {e}")
            raise
    
    def append_row(self, sheet_name: str, row_data: List[Any]):
        """
        Append single row to specified sheet.
        
        Args:
            sheet_name: Target sheet name
            row_data: List of values to append
            
        Returns:
            True if successful
        """
        try:
            worksheet = self.get_worksheet(sheet_name)
            worksheet.append_row(row_data)
            return True
        except Exception as e:
            logger.error(f"Failed to append row: {e}")
            return False
    
    def append_rows(self, sheet_name: str, rows_data: List[List[Any]]):
        """
        Append multiple rows to specified sheet (bulk operation).
        
        Args:
            sheet_name: Target sheet name
            rows_data: List of rows to append
            
        Returns:
            True if successful
        """
        if not rows_data:
            return False
            
        try:
            worksheet = self.get_worksheet(sheet_name)
            worksheet.append_rows(rows_data)
            logger.info(f"✅ Appended {len(rows_data)} rows to {sheet_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to append rows: {e}")
            return False
    
    def get_all_data(self, sheet_name: str) -> List[List[str]]:
        """
        Get all data from sheet including headers.
        
        Args:
            sheet_name: Target sheet name
            
        Returns:
            List of rows (including header row)
        """
        try:
            worksheet = self.get_worksheet(sheet_name)
            return worksheet.get_all_values()
        except Exception as e:
            logger.error(f"Failed to get data from {sheet_name}: {e}")
            return []
    
    def get_all_records(self, sheet_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all records as dictionaries.
        
        Args:
            sheet_name: Target sheet name (defaults to main sheet)
            
        Returns:
            List of dictionaries (header as keys)
        """
        try:
            worksheet = self.get_worksheet(sheet_name) if sheet_name else self.sheet
            return worksheet.get_all_records()
        except Exception as e:
            logger.error(f"Failed to get records: {e}")
            return []
    
    def update_cell(self, sheet_name: str, row: int, col: int, value: Any):
        """
        Update single cell value.
        
        Args:
            sheet_name: Target sheet name
            row: Row number (1-indexed)
            col: Column number (1-indexed)
            value: New value
            
        Returns:
            True if successful
        """
        try:
            worksheet = self.get_worksheet(sheet_name)
            worksheet.update_cell(row, col, value)
            return True
        except Exception as e:
            logger.error(f"Failed to update cell: {e}")
            return False
    
    def find_row(self, sheet_name: str, search_col: int, search_value: str) -> Optional[int]:
        """
        Find row number by searching in specific column.
        
        Args:
            sheet_name: Target sheet name
            search_col: Column to search in (1-indexed)
            search_value: Value to search for
            
        Returns:
            Row number if found, None otherwise
        """
        try:
            worksheet = self.get_worksheet(sheet_name)
            cell = worksheet.find(search_value, in_column=search_col)
            return cell.row if cell else None
        except Exception as e:
            logger.error(f"Failed to find row: {e}")
            return None
    
    # Legacy methods for backward compatibility
    
    @staticmethod
    def _clean_amount(amount_input) -> int:
        """Clean currency format to integer."""
        try:
            clean_str = re.sub(r'[^\d]', '', str(amount_input))
            return int(clean_str) if clean_str else 0
        except:
            return 0
    
    def add_transactions_bulk(self, transactions_list: List[Dict]) -> bool:
        """
        Add multiple transactions to main sheet.
        
        Args:
            transactions_list: List of transaction dictionaries
            
        Returns:
            True if successful
        """
        if not transactions_list:
            return False
        
        rows = []
        for t in transactions_list:
            amount = self._clean_amount(t.get('amount', 0))
            category = t.get('category', 'Uncategorized')
            is_income = str(category).lower() in ['income', 'pemasukan']
            
            rows.append([
                t.get('date', '-'),
                t.get('time', '-'),
                t.get('item', 'Unknown Item'),
                category,
                amount,  # Column 5: AMOUNTH(IDR) - Mixed Income/Expense
                t.get('location', '-') # Column 6: Location
            ])
        
        try:
            self.sheet.append_rows(rows)
            logger.info(f"✅ Added {len(rows)} transactions")
            return True
        except Exception as e:
            logger.error(f"Failed to add transactions: {e}")
            return False
    
    def get_all_transactions(self) -> List[Dict[str, Any]]:
        """Get all transactions from main sheet (Expenses)."""
        return self.get_all_records()

    def add_income_transactions(self, transactions_list: List[Dict]) -> bool:
        """Add income transactions to 'Budget' sheet."""
        if not transactions_list: return False
        
        rows = []
        for t in transactions_list:
            amount = self._clean_amount(t.get('amount', 0))
            rows.append([
                t.get('date', '-'),
                t.get('item', 'Income'),
                t.get('category', 'Income'),
                amount
            ])
        
        try:
            # Safely get or create the Budget sheet
            try:
                worksheet = self.spreadsheet.worksheet('Budget')
            except gspread.WorksheetNotFound:
                worksheet = self.spreadsheet.add_worksheet(title='Budget', rows=1000, cols=20)
                worksheet.append_row(['Date', 'Source', 'Type', 'Amount'])
                logger.info("✅ Created 'Budget' sheet with headers")
            
            # Check if headers exist (first cell should be 'Date')
            first_cell = worksheet.acell('A1').value
            if not first_cell or first_cell.strip() != 'Date':
                worksheet.insert_row(['Date', 'Source', 'Type', 'Amount'], 1)
            
            # Append data
            worksheet.append_rows(rows)
            logger.info(f"✅ Added {len(rows)} income records to Budget sheet")
            return True
        except Exception as e:
            logger.error(f"Failed to add income: {e}")
            return False

    def get_income_transactions(self) -> List[Dict[str, Any]]:
        """Get all income transactions from 'Budget' sheet."""
        return self.get_all_records('Budget')
    
    # AI System Support Methods
    
    def initialize_ai_sheets(self) -> bool:
        """
        Initialize all sheets required for AI system.
        Safe: won't duplicate existing sheets.
        """
        ai_sheets = {
            'UserProfiles': [
                'user_id', 'name', 'timezone', 'join_date',
                'last_active', 'preferences', 'communication_style'
            ],
            'ChatHistory': [
                'timestamp', 'user_id', 'message_type',
                'user_message', 'bot_response', 'context_used'
            ],
            'UserContext': [
                'user_id', 'total_spending_pattern', 'top_categories',
                'active_goals', 'achievements', 'sentiment_trend', 'last_updated'
            ],
            'KnowledgeBase': [
                'user_id', 'knowledge_type', 'knowledge_item',
                'confidence', 'learned_date', 'last_referenced'
            ]
        }
        
        try:
            for sheet_name, headers in ai_sheets.items():
                # create_worksheet is now safe (returns existing if found)
                self.create_worksheet(sheet_name, headers)
            
            logger.info("✅ AI sheets initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize AI sheets: {e}")
            return False
