import openpyxl
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font
from typing import List, Dict
import os
import logging

logger = logging.getLogger(__name__)

class ExcelExporter:
    def __init__(self):
        pass

    def generate_excel(self, leads: List[Dict], output_path: str = "linkedin_leads.xlsx") -> str:
        """
        Generates an Excel file from a list of lead dicts.
        Returns the path to the generated file.
        """
        if not leads:
            logger.warning("No leads provided to export.")
            return ""

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Leads"

        # Define columns and their order
        columns = [
            ("User Name", "user_name"),
            ("Profile URL", "profile_url"),
            ("Post Content", "post_content"),
            ("Posted Date", "posted_timestamp"),
            ("Post URL", "post_url"),
            ("Scraped At", "scraped_at"),
            ("Emailed", "is_emailed"),
            ("Search Query", "search_query_ref")
        ]

        # Write header
        for col_num, (header, _) in enumerate(columns, 1):
            cell = ws.cell(row=1, column=col_num, value=header)
            cell.font = Font(bold=True)

        # Write data rows
        for row_num, lead in enumerate(leads, 2):
            for col_num, (_, key) in enumerate(columns, 1):
                value = lead.get(key, "")
                ws.cell(row=row_num, column=col_num, value=value)

        # Auto-size columns
        for col_num, (header, _) in enumerate(columns, 1):
            col_letter = get_column_letter(col_num)
            ws.column_dimensions[col_letter].width = max(15, len(header) + 2)

        # Save file
        wb.save(output_path)
        logger.info(f"Excel file generated: {os.path.abspath(output_path)}")
        return os.path.abspath(output_path)

# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from data_manager import DataManager
    dm = DataManager()
    leads = dm.get_new_leads()
    exporter = ExcelExporter()
    exporter.generate_excel(leads, "linkedin_leads_test.xlsx")
    dm.close() 