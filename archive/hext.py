# Replace heading tags with paragraph tag
for heading_level in range(1, 7):
    heading_tag_half_open, heading_tag_full_open, heading_tag_close = f"<h{heading_level} ", f"<h{heading_level}>", f"</h{heading_level}>"
    if heading_tag_close in html:
        html = html.replace(heading_tag_half_open, "<p ")
        html = html.replace(heading_tag_full_open, "<p>")
        html = html.replace(heading_tag_close, "</p>")
        # print(f"Replaced h{heading_level} with p tags.")