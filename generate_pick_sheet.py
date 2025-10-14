from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter

def generate_pick_sheet(c, customer_data, boxed=False):
    """
    Generate a pick sheet PDF page(s) for a customer.

    Args:
        c: ReportLab canvas object.
        customer_data (dict): Contains 'name', 'username', 'address', 'items', and optional 'uid' and 'num_items'.
        boxed (bool): If True, draws a box around the UID and item total.

    Returns:
        int: Number of pages generated.
    """
    num_pages = 1
    width, height = letter
    margin = 30
    y_start = height - margin - 30

    def draw_header():
        nonlocal y_start
        c.setFont("Helvetica-Bold", 20)
        c.drawString(margin, y_start, customer_data['username'] + " ")

        c.setFont("Helvetica", 14)
        username_width = c.stringWidth(customer_data['username'] + " ", "Helvetica-Bold", 20)
        c.drawString(margin + username_width, y_start, customer_data['name'])

        c.setFont("Helvetica", 100)
        uid_text = "{:03}".format(customer_data.get('uid', ''))
        uid_width = c.stringWidth(uid_text, "Helvetica", 100)
        c.drawString(width - margin - uid_width, y_start - 65, uid_text)

        if boxed:
            x = width - margin - uid_width
            y = y_start - 70
            padding = 5
            c.setLineWidth(5)
            c.rect(x - padding, y - padding, uid_width + 2 * padding, 90, stroke=1, fill=0)
            c.setLineWidth(1)

        y_start -= 25
        c.setFont("Helvetica", 14)
        c.drawString(margin, y_start, customer_data['address'])

        def get_order_date_range(items):
            dates = []
            for item in items:
                try:
                    dates.append(datetime.strptime(str(item['time']), "%Y-%m-%d %H:%M:%S"))
                except:
                    continue
            return (min(dates).date(), max(dates).date()) if dates else (None, None)

        min_date, max_date = get_order_date_range(customer_data['items'])
        if min_date and max_date:
            y_start -= 25
            c.setFont("Helvetica-Bold", 18)
            c.drawString(margin, y_start, max_date.strftime("%A"))

            cur_width = c.stringWidth(max_date.strftime("%A"), "Helvetica-Bold", 18)
            c.setFont("Helvetica", 14)
            c.drawString(margin + cur_width, y_start, ", " + max_date.strftime("%b %d"))

            if min_date != max_date:
                cur_width += c.stringWidth(", " + max_date.strftime("%b %d"), "Helvetica", 14)
                c.drawString(margin + cur_width, y_start, " to ")
                cur_width += c.stringWidth(" to ", "Helvetica", 14)
                c.drawString(margin + cur_width, y_start, min_date.strftime("%A, %b %d"))

        y_start -= 30
        c.setFont("Helvetica-Bold", 14)
        c.setStrokeColor(colors.black)
        c.line(margin, y_start, width - margin, y_start)
        y_start -= 17

    def draw_footer():
        nonlocal num_items
        c.setFont("Helvetica-Bold", 40)

        total = str(customer_data.get('num_items', len(customer_data['items'])))
        total_items_width = c.stringWidth(total, "Helvetica-Bold", 40)
        x, y = margin, margin + 20
        c.drawString(x, y, total)

        if boxed:
            c.setLineWidth(3)
            c.rect(x - 5, y - 5, total_items_width + 10, 40, stroke=1, fill=0)
            c.setLineWidth(1)

        c.setFont("Helvetica", 10)
        label_x = x + total_items_width + (8 if boxed else 0)
        c.drawString(label_x, y, " " + str(num_items))

    draw_header()
    num_items = 0

    for item in customer_data['items']:
        c.setFont("Helvetica", 14)
        title = item['title']
        if ("hold" in title.lower() or "cancel" in title.lower()):
            c.setFont("Helvetica-Bold", 14)
        c.rect(margin, y_start - 1, 12, 12, stroke=1, fill=0)
        c.drawString(margin + 20, y_start, title)
        num_items += 1
        y_start -= 7
        c.line(margin, y_start, width - margin, y_start)
        y_start -= 17

        if y_start < margin + 60:
            draw_footer()
            c.showPage()
            num_pages += 1
            num_items = 0
            y_start = height - margin - 30
            draw_header()

    draw_footer()
    return num_pages