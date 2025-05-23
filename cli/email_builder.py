from typing import List, Dict
import html

class EmailBuilder:
    def generate_html_table(self, leads_data: list[dict]) -> str:
        if not leads_data:
            return "<p>No new leads found in this report.</p>"

        html_content = "<html><head><style>"
        html_content += """
            body { font-family: sans-serif; margin: 20px; }
            h2 { color: #333; }
            table { border-collapse: collapse; width: 100%; margin-top: 20px; font-size: 0.9em; }
            th, td { border: 1px solid #ddd; padding: 10px; text-align: left; }
            th { background-color: #f2f2f2; color: #333; }
            tr:nth-child(even) { background-color: #f9f9f9; }
            tr:hover { background-color: #e9e9e9; }
            a { color: #0066cc; text-decoration: none; }
            a:hover { text-decoration: underline; }
            .post-content { max-width: 400px; white-space: pre-wrap; word-wrap: break-word; }
        """
        html_content += "</style></head><body>"
        html_content += "<h2>LinkedIn Leads Report</h2>"
        html_content += "<table border='1'><thead><tr>"
        html_content += "<th>User Name</th><th>Post Content</th><th>Posted Date</th><th>Profile URL</th><th>Post URL</th>"
        html_content += "</tr></thead><tbody>"

        for lead in leads_data:
            html_content += "<tr>"
            html_content += f"<td>{html.escape(str(lead.get('user_name', 'N/A')))}</td>"
            html_content += f"<td class='post-content'>{html.escape(str(lead.get('post_content', 'N/A')))}</td>"
            
            posted_timestamp_str = 'N/A'
            posted_timestamp = lead.get('posted_timestamp')
            if posted_timestamp:
                # Assuming posted_timestamp is a datetime object or a string that can be directly used.
                # If it's a datetime object, format it. If it's already a string, use it as is.
                try:
                    posted_timestamp_str = posted_timestamp.strftime('%Y-%m-%d %H:%M')
                except AttributeError:
                    posted_timestamp_str = str(posted_timestamp) # Fallback if not a datetime object
            
            html_content += f"<td>{html.escape(posted_timestamp_str)}</td>"
            
            profile_url = lead.get('profile_url', '#')
            post_url = lead.get('post_url', '#')
            
            html_content += f"<td><a href='{html.escape(profile_url)}'>{html.escape(profile_url)}</a></td>"
            html_content += f"<td><a href='{html.escape(post_url)}'>{html.escape(post_url)}</a></td>"
            html_content += "</tr>"
        
        html_content += "</tbody></table></body></html>"
        return html_content

# Example Usage (for testing this module directly)
if __name__ == "__main__":
    from datetime import datetime, timedelta
    builder = EmailBuilder()

    # Test with no leads
    print("--- Testing with no leads ---")
    empty_html = builder.generate_html_table([])
    print(empty_html)
    with open("email_preview_empty.html", "w", encoding="utf-8") as f:
        f.write(empty_html)
    print("Saved to email_preview_empty.html\n")

    # Test with sample leads
    sample_leads = [
        {
            "user_name": "Alice Wonderland",
            "post_content": "Excited to announce my new project! #innovation #tech\nIt involves a lot of interesting challenges.",
            "posted_timestamp": datetime.now() - timedelta(days=1),
            "profile_url": "http://linkedin.com/in/alicew",
            "post_url": "http://linkedin.com/feed/post/alice123"
        },
        {
            "user_name": "Bob The Builder",
            "post_content": "Looking for collaborators for a construction tech solution. DM me if interested! <script>alert('xss')</script>",
            "posted_timestamp": "2023-10-25 10:30:00", # Test with string date
            "profile_url": "http://linkedin.com/in/bobtheb",
            "post_url": "http://linkedin.com/feed/post/bob456"
        },
        {
            "user_name": "Charles Xavier",
            # Missing some fields to test defaults
            "profile_url": "http://linkedin.com/in/charlesx",
        }
    ]
    print("--- Testing with sample leads ---")
    html_table = builder.generate_html_table(sample_leads)
    print(html_table)
    # For easier review, save to an HTML file
    with open("email_preview_leads.html", "w", encoding="utf-8") as f:
        f.write(html_table)
    print("Saved to email_preview_leads.html") 