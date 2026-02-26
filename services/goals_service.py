import gspread
from google.oauth2.service_account import Credentials
from config import Config
import os
import json
import time

class GoalsService:
    def __init__(self):
        self.client = self._get_gspread_client()
        self.sheet = self._get_or_create_sheet(Config.SHEET_GOALS)

    def _get_gspread_client(self):
        # Duplikasi logic auth dari SheetsService agar tidak mengubah code existing
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
                # Buat sheet baru jika belum ada
                worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=100, cols=5)
                # Header
                worksheet.append_row(["Goal Name", "Target Amount", "Saved Amount", "Created Date", "Note"])
            return worksheet
        except Exception as e:
            print(f"❌ Error accessing Goals sheet: {e}")
            return None

    def set_goal(self, name, target_amount, note="-"):
        if not self.sheet: return False
        
        # Cek duplikat
        goals = self.get_goals()
        for g in goals:
            if g.get("Goal Name").lower() == name.lower():
                return False # Goal already exists
        
        from datetime import datetime
        created_date = datetime.now().strftime("%Y-%m-%d")
        
        self.sheet.append_row([name, target_amount, 0, created_date, note])
        return True

    def get_goals(self):
        if not self.sheet: return []
        try:
            return self.sheet.get_all_records()
        except:
            return []

    def delete_goal(self, name):
        if not self.sheet: return False
        try:
            cell = self.sheet.find(name)
            if cell:
                self.sheet.delete_rows(cell.row)
                return True
            return False
        except:
            return False

    def get_formatted_goals_progress(self, current_savings=0):
        # Note: Current logic assumes 'Saved Amount' is manually updated or calculated globally.
        # For simplicity in this Phase, we might just compare Target vs (Allocated Savings).
        # But PRD implies tracking. 
        # Untuk MVP Phase 3 ini, kita akan hitung progress dari TABUNGAN MANUAL atau 
        # kita asumsikan user punya "Income" - "Expense" = Savings.
        
        # Sesuai instruksi simple, kita baca data dari sheet Goals saja.
        goals = self.get_goals()
        if not goals:
            return "Belum ada Goal yang diset. Pakai /setgoal <nama> <target>"

        msg = "🎯 **Financial Goals**\n\n"
        for g in goals:
            name = g.get('Goal Name')
            target = int(g.get('Target Amount') or 0)
            saved = int(g.get('Saved Amount') or 0)
            
            # Simple bar
            progress = min(1.0, saved / target) if target > 0 else 0
            bar_len = 10
            filled = int(progress * bar_len)
            bar = "▓" * filled + "░" * (bar_len - filled)
            pct = int(progress * 100)
            
            msg += f"📌 **{name}**\n"
            msg += f"{bar} {pct}%\n"
            msg += f"Rp {saved:,} / Rp {target:,}\n\n"
            
        return msg
