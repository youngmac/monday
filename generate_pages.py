from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from weather import get_alerting_forecast
import config
from predicates import is_important, is_plant, is_tc, could_be_plant, could_be_tc

# TODO get rid of magic number ;)

def generate_pick_sheet(c, customer_data, boxed=False):
    """
    Generate a pick sheet PDF page(s) for a customer.
    """

    num_pages = 1
    width, height = letter
    y_start = height - config.MARGIN - 30

    def draw_forecast_chart(forecast, x=50, y=100, width=500):
        """
        Draws a simple forecast chart with:
        - First and last dates include full date (e.g., Mon, 10/13)
        - Middle dates show only weekday (e.g., Tue)
        - Shows all max temps if any day is > 88
        - Shows all min temps if any day is < 40
        """
        if not forecast or "time" not in forecast:
            c.setFont(*config.NO_FORCAST_DATA_FONT)
            c.drawString(x, y, "No forecast data available. Please look up weather manually!")
            return

        dates = forecast["time"]
        max_temps = forecast["temperature_2m_max"]
        min_temps = forecast["temperature_2m_min"]

        show_max = any(t > config.MAX_ACCEPTABLE_TEMP for t in max_temps)
        show_min = any(t < config.MIN_ACCEPTABLE_TEMP for t in min_temps)

        if not (show_max or show_min):
            return  # Nothing to draw

        num_days = len(dates)
        day_spacing = (width + 50) / num_days

        c.setFont(*config.FORECAST_LABEL_FONT)

        for i in range(num_days):
            date_obj = datetime.strptime(dates[i], "%Y-%m-%d")

            # Show full date on first and last day
            if i == 0 or i == num_days - 1:
                label = date_obj.strftime("%a, %m/%d")
            else:
                label = date_obj.strftime("%a")

            x_pos = x + i * day_spacing

            # Draw day label
            c.drawString(x_pos, y + 15, label)

            # Build temp string
            temp_label = ""
            if show_max:
                temp_label += f"{int(max_temps[i])}°"
            if show_min:
                if temp_label:
                    temp_label += " / "
                temp_label += f"{int(min_temps[i])}°"

            # Draw temp label
            if (int(max_temps[i]) > config.MAX_ACCEPTABLE_TEMP or int(min_temps[i]) < config.MIN_ACCEPTABLE_TEMP):
                c.setFont(*config.EXTREME_TEMP_LABEL_FONT)
            else:
                c.setFont(*config.TEMP_LABEL_FONT)
            c.drawString(x_pos, y, temp_label)
            c.setFont(*config.FORECAST_LABEL_FONT)

    def draw_header():
        nonlocal y_start
        c.setFont("Helvetica-Bold", 20)
        c.drawString(config.MARGIN, y_start, customer_data['username'] + " ")

        c.setFont("Helvetica", 14)
        username_width = c.stringWidth(customer_data['username'] + " ", "Helvetica-Bold", 20)
        c.drawString(config.MARGIN + username_width, y_start, customer_data['name'])

        c.setFont("Helvetica", 100)
        uid_text = "{:03}".format(customer_data.get('uid', ''))
        uid_width = c.stringWidth(uid_text, "Helvetica", 100)
        c.drawString(width - config.MARGIN - uid_width, y_start - 65, uid_text)

        if boxed:
            x = width - config.MARGIN - uid_width
            y = y_start - 70
            padding = 5
            c.setLineWidth(5)
            c.rect(x - padding, y - padding, uid_width + 2 * padding, 90, stroke=1, fill=0)
            c.setLineWidth(1)

        y_start -= 25
        c.setFont("Helvetica", 14)
        c.drawString(config.MARGIN, y_start, customer_data['address'])

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
            c.drawString(config.MARGIN, y_start, max_date.strftime("%A"))

            cur_width = c.stringWidth(max_date.strftime("%A"), "Helvetica-Bold", 18)
            c.setFont("Helvetica", 14)
            c.drawString(config.MARGIN + cur_width, y_start, ", " + max_date.strftime("%b %d"))

            if min_date != max_date:
                cur_width += c.stringWidth(", " + max_date.strftime("%b %d"), "Helvetica", 14)
                c.drawString(config.MARGIN + cur_width, y_start, " to ")
                cur_width += c.stringWidth(" to ", "Helvetica", 14)
                c.drawString(config.MARGIN + cur_width, y_start, min_date.strftime("%A, %b %d"))

        # Add the weather forecast chart
        forecast = get_alerting_forecast(customer_data['address'])
        if forecast or forecast == {}:
            y_start -= 50
            draw_forecast_chart(forecast, x=config.MARGIN, y=y_start)
            y_start += 20

        y_start -= 30
        c.setFont("Helvetica-Bold", 14)
        c.setStrokeColor(colors.black)
        c.line(config.MARGIN, y_start, width - config.MARGIN, y_start)
        y_start -= 17

    def draw_footer():
        # Total number items/number items on this page
        nonlocal num_items
        c.setFont("Helvetica-Bold", 40)

        total = str(customer_data.get('num_items', len(customer_data['items'])))
        total_items_width = c.stringWidth(total, "Helvetica-Bold", 40)
        x, y = config.MARGIN, config.MARGIN + 20
        c.drawString(x, y, total)

        if boxed:
            c.setLineWidth(3)
            c.rect(x - 5, y - 5, total_items_width + 10, 40, stroke=1, fill=0)
            c.setLineWidth(1)

        c.setFont("Helvetica", 10)
        label_x = x + total_items_width + (8 if boxed else 0)
        c.drawString(label_x, y, " " + str(num_items))

        # Draw CP and HP section at bottom center
        section_y = config.MARGIN + 5
        c.setFont(*config.CP_HP_FONT)

        cp_label = "CP ______"
        hp_label = "HP ______"

        # Get total width of the two sections with a bit of spacing
        spacing = 30
        cp_width = c.stringWidth(cp_label, *config.CP_HP_FONT)
        hp_width = c.stringWidth(hp_label, *config.CP_HP_FONT)
        total_section_width = cp_width + spacing + hp_width

        center_x = (width - total_section_width) / 2
        c.drawString(center_x - 30, section_y + 20, cp_label)
        c.drawString(center_x - 30 + cp_width + spacing, section_y + 20, hp_label)

    draw_header()
    num_items = 0

    for item in customer_data['items']:
        c.setFont(*config.ITEM_FONT)
        title = item['title']
        if (is_important(title)):
            c.setFont(*config.ITEM_IMPORTANT_FONT)
        c.rect(config.MARGIN, y_start - 1, 12, 12, stroke=1, fill=0)
        c.drawString(config.MARGIN + 20, y_start, title)
        num_items += 1
        y_start -= 7
        c.line(config.MARGIN, y_start, width - config.MARGIN, y_start)
        y_start -= 17

        if y_start < config.MARGIN + 60:
            draw_footer()
            c.showPage()
            num_pages += 1
            num_items = 0
            y_start = height - config.MARGIN - 30
            draw_header()

    draw_footer()
    return num_pages
def generate_order_summary(c, aggregated_data, plants):
    """
    Draws an order summary on the provided canvas.

    Args:
        c: reportlab.pdfgen.canvas.Canvas - the canvas to draw on.
        aggregated_data: dict - {item_name: quantity}
        plants: list of strings - plant names (each counted as 1, but not displayed with quantity)

    Returns:
        int: number of pages used
    """
    width, height = letter
    margin = 50
    line_height = 16
    start_y = height - margin
    y = start_y
    page_count = 1

    # Title
    c.setFont("Helvetica-Bold", 18)
    c.drawString(margin, y, "Order Summary")
    y -= 2 * line_height

    # Header for regular items
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, y, "Item")
    c.drawRightString(width - margin, y, "Qty")
    y -= line_height
    c.setFont("Helvetica", 10)

    # Draw aggregated items
    for item, quantity in aggregated_data.items():
        if y < margin + 6 * line_height:  # page break margin
            c.showPage()
            page_count += 1
            y = start_y
            c.setFont("Helvetica-Bold", 18)
            c.drawString(margin, y, "Order Summary (cont'd)")
            y -= 2 * line_height
            c.setFont("Helvetica-Bold", 12)
            c.drawString(margin, y, "Item")
            c.drawRightString(width - margin, y, "Qty")
            y -= line_height
            c.setFont("Helvetica", 10)

        # Draw item and quantity
        c.drawString(margin, y, item)
        c.drawRightString(width - margin, y, str(quantity))

        # Draw horizontal line under the row
        y_line = y - 2  # slight offset
        c.setLineWidth(0.25)
        c.line(margin, y_line, width - margin, y_line)

        y -= line_height

    # Space before plant section
    y -= 2 * line_height

    # Start plant section
    if y < margin + (len(plants) + 4) * line_height:
        c.showPage()
        page_count += 1
        y = start_y

    c.setFont("Helvetica-Bold", 14)
    c.drawString(margin, y, "Plant List")
    y -= 2 * line_height
    c.setFont("Helvetica", 10)

    for plant in plants:
        if y < margin + 2 * line_height:
            c.showPage()
            page_count += 1
            y = start_y
            c.setFont("Helvetica-Bold", 14)
            c.drawString(margin, y, "Plant List (cont'd)")
            y -= 2 * line_height
            c.setFont("Helvetica", 10)

        c.drawString(margin, y, plant)
        y -= line_height

    # Space and total count
    y -= line_height
    if y < margin + line_height:
        c.showPage()
        page_count += 1
        y = start_y

    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, y, f"Total plants: {len(plants)}")

    c.showPage()
    return page_count


def generate_customer_summary(c, customers):
    width, height = letter
    margin = 50
    line_height = 16
    start_y = height - margin
    y = start_y
    page_count = 1

    user_x = margin
    item_x = width - margin

    def new_page(title="Single Item Orders"):
        nonlocal y, page_count
        c.showPage()
        page_count += 1
        y = start_y
        c.setFont("Helvetica-Bold", 16)
        c.drawString(user_x, y, title)
        y -= 2 * line_height
        c.setFont("Helvetica", 10)

    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(user_x, y, "Single Item Orders")
    y -= 2 * line_height
    c.setFont("Helvetica", 10)

    # Build list of (username, item_title)
    entries = []
    for cust in customers:
        username = cust['username']
        for item in cust['items']:
            title = item['title']
            entries.append((username, title))

    # Sort with custom logic
    def sort_key(entry):
        _, title = entry
        return (
            not is_tc(title),             # False (is_tc) comes first
            not could_be_tc(title),       # then could_be_tc
            not is_plant(title),          # then is_plant
            not could_be_plant(title),    # then could_be_plant
            title.lower()                 # finally alphabetical
        )

    entries.sort(key=sort_key)

    for username, item_title in entries:
        if y < margin + line_height:
            new_page("Single Item Orders (cont'd)")
        c.drawString(user_x, y, username)
        c.drawRightString(item_x, y, item_title)
        y -= line_height

    # Total
    if y < margin + 2 * line_height:
        new_page("Single Item Orders (cont'd)")
    y -= line_height
    c.setFont("Helvetica-Bold", 11)
    c.drawString(user_x, y, f"Total orders: {len(customers)}")

    c.showPage()
    return page_count