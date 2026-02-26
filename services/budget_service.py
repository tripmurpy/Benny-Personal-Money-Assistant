import gspread
from google.oauth2.service_account import Credentials
from config import Config
import os
import json
from datetime import datetime

class BudgetService:
    def __init__(self):
        self.client = self._get_gspread_client()
        self.sheet = self._get_or_create_sheet(Config.SHEET_BUDGETS)

    def _get_gspread_client(self):
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        json_creds = os.getenv("GOOGLE_CREDENTIALS_JSON")
        if json_creds:
            creds_dict = json.loads(json_creds)
            creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        else:
            creds = Credentials.from_service_account_file(Config.GOOGLE_CREDS_PATH, scopes=scopes)
            
        return gspread.authorize(creds)

    def _get_or_create_sheet(self, sheet_name):
        try:
            spreadsheet = self.client.open_by_key(Config.SPREADSHEET_ID)
            try:
                worksheet = spreadsheet.worksheet(sheet_name)
            except gspread.WorksheetNotFound:
                worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=100, cols=3)
                worksheet.append_row(["Category", "Monthly Limit", "Last Updated"])
            return worksheet
        except Exception as e:
            print(f"❌ Error accessing Budgets sheet: {e}")
            return None

    def set_budget(self, category, limit):
        if not self.sheet: return False
        
        # Cek apakah kategori sudah ada
        try:
            cell = self.sheet.find(category)
            date_now = datetime.now().strftime("%Y-%m-%d")
            
            if cell:
                # Update
                self.sheet.update_cell(cell.row, 2, limit)
                self.sheet.update_cell(cell.row, 3, date_now)
            else:
                # Insert new
                self.sheet.append_row([category, limit, date_now])
            return True
        except Exception as e:
            print(f"Error set budget: {e}")
            return False

    def get_budgets(self):
        if not self.sheet: return {}
        try:
            records = self.sheet.get_all_records()
            # Convert ke dict {Category: Limit}
            budget_map = {}
            for r in records:
                try:
                    cat = r.get('Category')
                    limit = int(r.get('Monthly Limit') or 0)
                    if cat:
                        budget_map[cat.lower()] = limit
                except:
                    pass
            return budget_map
        except:
            return {}

    def delete_budget(self, category):
        if not self.sheet: return False
        try:
            cell = self.sheet.find(category)
            if cell:
                self.sheet.delete_rows(cell.row)
                return True
            return False
        except:
            return False

    def top_up_budget(self, category: str, amount: int) -> tuple[bool, int]:
        """Add amount to existing budget limit. Returns (success, new_limit)."""
        budgets = self.get_budgets()
        cat_lower = category.lower()
        
        if cat_lower not in budgets:
            return False, 0
        
        old_limit = budgets[cat_lower]
        new_limit = old_limit + amount
        
        # Use set_budget to update (it handles find + update)
        if self.set_budget(category, new_limit):
            return True, new_limit
        return False, 0

    def deduct_budget(self, category: str, amount: int) -> tuple[int, int]:
        """
        Deduct amount from budget. 
        Returns (amount_deducted_from_budget, amount_excess_to_general).
        If budget is 100k and spend 120k -> returns (100k, 20k).
        """
        budgets = self.get_budgets()
        cat_lower = category.lower()
        
        if cat_lower not in budgets:
            return 0, amount # No budget, all excess
        
        current_limit = budgets[cat_lower]
        
        if current_limit >= amount:
            # Enough budget
            new_limit = current_limit - amount
            self.set_budget(category, new_limit)
            return amount, 0
            
        else:
            # Overflow
            excess = amount - current_limit
            deducted = current_limit
            
            # Set budget to 0 (empty)
            self.set_budget(category, 0)
            
            return deducted, excess

