from typing import List, Dict
import html

class EmailBuilder:
    def __init__(self):
        pass

    def generate_html_table(self, leads: List[Dict]) -> str:
        """
        Generates an HTML table from a list of lead dicts.
        Returns the HTML string.
        """
        if not leads:
            return "<p>No leads found.</p>"

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

        html_table = [
            '<table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse;font-family:sans-serif;font-size:13px;">',
            '<thead><tr>' + ''.join(f'<th>{html.escape(header)}</th>' for header, _ in columns) + '</tr></thead>',
            '<tbody>'
        ]

        for lead in leads:
            html_table.append('<tr>')
            for _, key in columns:
                value = lead.get(key, "")
                if key in ("profile_url", "post_url") and value:
                    value = f'<a href="{html.escape(str(value))}">{html.escape(str(value))}</a>'
                else:
                    value = html.escape(str(value))
                html_table.append(f'<td>{value}</td>')
            html_table.append('</tr>')

        html_table.append('</tbody></table>')
        return '\n'.join(html_table)

# Example usage
def _test():
    from data_manager import DataManager
    dm = DataManager()
    leads = dm.get_new_leads()
    builder = EmailBuilder()
    html_str = builder.generate_html_table(leads)
    print(html_str)
    dm.close()

if __name__ == "__main__":
    _test() 