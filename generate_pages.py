from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from weather import get_alerting_forecast
import config
from predicates import is_important, is_plant, is_tc, could_be_plant, could_be_tc, is_any_plant
from reportlab.pdfbase import pdfmetrics
from datetime import date
from order_utils import name_address_to_key


# TODO get rid of magic number ;)

def draw_forecast_chart(c, forecast, x=50, y=100, width=500):
    """
    Draws a simple forecast chart with:
    - First and last dates include full date (e.g., Mon, 10/13)
    - Middle dates show only weekday (e.g., Tue)
    - Shows all max temps if any day is > 88
    - Shows all min temps if any day is < 40
    """
    if forecast is None:
        return 1 # Nothing to draw
    
    if forecast == {} or "time" not in forecast:
        c.setFont(*config.NO_FORCAST_DATA_FONT)
        c.drawString(x, y, "No forecast data available. Please look up weather manually!")
        return 2

    dates = forecast["time"]
    max_temps = forecast["temperature_2m_max"]
    min_temps = forecast["temperature_2m_min"]

    show_max = any(t > config.MAX_ACCEPTABLE_TEMP for t in max_temps)
    show_min = any(t < config.MIN_ACCEPTABLE_TEMP for t in min_temps)

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
    return 0

def generate_pick_sheet(c, customer_data, boxed=False, double_boxed=False):
    """
    Generate a pick sheet PDF page(s) for a customer.
    """

    num_pages = 1
    width, height = letter
    y_start = height - config.MARGIN - 30

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

        if boxed and not double_boxed:
            x = width - config.MARGIN - uid_width
            y = y_start - 70
            padding = 5
            c.setLineWidth(5)
            c.rect(x - padding, y - padding, uid_width + 2 * padding, 90, stroke=1, fill=0)
            c.setLineWidth(1)
        elif double_boxed:
            x = width - config.MARGIN - uid_width
            y = y_start - 70
            padding_outer = 8
            padding_inner = 4
            c.setLineWidth(1)
            c.rect(x - padding_outer, y - padding_outer, uid_width + 2 * padding_outer, 98, stroke=1, fill=0)
            c.setLineWidth(1)
            c.rect(x - padding_inner, y - padding_inner, uid_width + 2 * padding_inner, 90, stroke=1, fill=0)
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

        # 2-day shipping indicator
        if customer_data["2day"]:
            y_start -= 22
            c.setFont("Helvetica-Bold", 14)
            c.drawString(config.MARGIN, y_start, "                    ** 2-DAY AIR UPS SHIPPING **")
            y_start += 20
        if customer_data["1day"]:
            y_start -= 22
            c.setFont("Helvetica-Bold", 14)
            c.drawString(config.MARGIN, y_start, "                    ** NEXT DAY AIR UPS SHIPPING **")
            y_start += 20

        # Add the weather forecast chart
        forecast = get_alerting_forecast(customer_data['address'])
        if forecast or forecast == {}:
            y_start -= 50
            draw_forecast_chart(c, forecast, x=config.MARGIN, y=y_start)
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
        items_total = 0
        for item in customer_data['items']:
            items_total += item.get('quantity', 1)

        total = str(customer_data.get('num_items', items_total))
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

    def draw_cost_footer():
        nonlocal total_cost
        nonlocal plant_cost
        nonlocal ship_cost
        nonlocal subtotal
        nonlocal y_start

        # Height needed for this footer line
        line_height = 16

        # If the remaining space is too small, start a new page
        if y_start < config.MARGIN + line_height + 60:
            draw_footer()
            c.showPage()
            # reset page and header
            y_start = height - config.MARGIN - 30
            draw_header()

        # Draw cost line (bold)
        c.setFont("Helvetica-Bold", 14)
        cost_line = f"~Shipping: ${ship_cost:.2f}    ~Plants: ${plant_cost:.2f}    Subtotal: ${subtotal:.2f}    ~Total: ${total_cost:.2f}"
        c.drawString(config.MARGIN, y_start, cost_line)

        # Move cursor downward slightly for final footer spacing
        y_start -= line_height
        

    draw_header()
    num_items = 0
    total_cost = customer_data.get('costs', {}).get('total_cost', 0.0)
    plant_cost = customer_data.get('costs', {}).get('plant_cost', 0.0)
    ship_cost = customer_data.get('costs', {}).get('ship_cost', 0.0)
    subtotal = customer_data.get('costs', {}).get('subtotal', 0.0)

    

    for item in customer_data['items']:
        # Default font for regular items
        c.setFont(*config.ITEM_FONT)

        title = item['title']
        qty = item.get('quantity', 1)

        # If the item title is important, use the special font
        if is_important(title):
            c.setFont(*config.ITEM_IMPORTANT_FONT)

        # Draw checkbox rectangle
        c.rect(config.MARGIN, y_start - 1, 12, 12, stroke=1, fill=0)

        # --- Format and Draw Quantity ---
        qty_str = f"{qty}" if qty > 1 else ""
        # Use bold font for quantity (regardless of importance)
        c.setFont(*config.ITEM_IMPORTANT_FONT)
        qty_x = config.MARGIN + 20
        c.drawString(qty_x, y_start, f"{qty_str:>3}")  # right-align within small space

        # --- Draw Title ---
        title_x = config.MARGIN + 55  # fixed offset so all titles align
        # Reset font (important or normal)
        if is_important(title):
            c.setFont(*config.ITEM_IMPORTANT_FONT)
        else:
            c.setFont(*config.ITEM_FONT)

        c.drawString(title_x, y_start, title)

        # --- Draw Price (right aligned) ---
        qty_str = qty_str + " x " if qty > 1 else ""
        price = item.get("price", 0.0)
        price_str = qty_str + f"${price:,.2f}"
        price_x = width - config.MARGIN
        c.setFont("Helvetica", 12)
        c.drawRightString(price_x, y_start, price_str)

        # --- Draw Line Separator ---
        num_items += qty
        y_start -= 7
        c.line(config.MARGIN, y_start, width - config.MARGIN, y_start)
        y_start -= 17

        # --- Handle Pagination ---
        if y_start < config.MARGIN + 60:
            draw_footer()
            c.showPage()
            num_pages += 1
            num_items = 0
            y_start = height - config.MARGIN - 30
            draw_header()

    draw_cost_footer()
    draw_footer()
    return num_pages

def generate_order_summary(c, aggregated_data, plants, date):
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
    c.drawString(margin, y, "Order Summary" + date.strftime(" for %A, %B %d, %Y"))
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
            c.drawString(margin, y, "Order Summary (cont'd)" + date.strftime(" for %A, %B %d, %Y"))
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
    c.drawString(margin, y, "Plant List" + date.strftime(" for %A, %B %d, %Y"))
    y -= 2 * line_height
    c.setFont("Helvetica", 10)

    for plant in plants:
        if y < margin + 2 * line_height:
            c.showPage()
            page_count += 1
            y = start_y
            c.setFont("Helvetica-Bold", 14)
            c.drawString(margin, y, "Plant List (cont'd)" + date.strftime(" for %A, %B %d, %Y"))
            y -= 2 * line_height
            c.setFont("Helvetica", 10)

        c.drawString(margin, y, plant)
        c.drawRightString(width - config.MARGIN, y, f"${plants.get(plant, 0.0):,.2f}")
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


def generate_customer_summary(c, customers, date):
    width, height = letter
    margin = 50
    line_height = 16
    start_y = height - margin
    y = start_y
    page_count = 1

    user_x = margin
    item_x = width - margin

    def new_page(date, title="Single Item Orders"):
        nonlocal y, page_count
        c.showPage()
        page_count += 1
        y = start_y
        c.setFont("Helvetica-Bold", 16)
        c.drawString(user_x, y, title + date.strftime(" for %A, %B %d, %Y"))
        y -= 2 * line_height
        c.setFont("Helvetica", 10)

    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(user_x, y, "Single Item Orders" + date.strftime(" for %A, %B %d, %Y"))
    y -= 2 * line_height
    c.setFont("Helvetica", 10)

    # Build list of (username, item_title, forecast)
    entries = []
    cust_index = 1
    for cust in customers:
        username = cust['username']
        for item in cust['items']:
            title = item['title']
            print(f"Getting weather for single item order {username} ... {cust_index}/{len(customers)}")
            cust_index += 1
            forecast = get_alerting_forecast(cust['address'])
            entries.append((username, cust["state"], title, forecast))

    # Sort with custom logic
    def sort_key(entry):
        _, _, title, _ = entry
        return (
            not is_tc(title),             # False (is_tc) comes first
            not could_be_tc(title),       # then could_be_tc
            not is_plant(title),          # then is_plant
            not could_be_plant(title),    # then could_be_plant
            title.lower()                 # finally alphabetical
        )

    entries.sort(key=sort_key)

    for username, state, item_title, forecast in entries:
        if y - 50 < margin + line_height:
            new_page(date, "Single Item Orders ")
        y -= line_height - 10
        c.drawString(user_x, y, username + ", " + state)
        c.drawRightString(item_x, y, item_title)
        y -= line_height

        # Always attempt to draw if we got *any* forecast result
        y -= 20
        result = draw_forecast_chart(c, forecast or {}, x=config.MARGIN, y=y)

        if result == 1:
            y += 10
        elif result == 2:
            y += 0  # optional spacing tweak
        c.setFont("Helvetica", 10)
        c.setStrokeColor(colors.black)
        y -= 5
        c.line(config.MARGIN, y, width - config.MARGIN, y)
        y -= 10

    # Total
    if y < margin + 2 * line_height:
        new_page(date, "Single Item Orders (cont'd) ")
    y -= line_height
    c.setFont("Helvetica-Bold", 11)
    c.drawString(user_x, y, f"Total orders: {len(customers)}")

    c.showPage()
    return page_count

def generate_holds_report(c, holds):
    """
    Generate a PDF report of holds using ReportLab.
    Returns the number of pages created.
    """
    width, height = letter

    # Title with max_date
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, f"Hold Orders Report (Up to {date.today().strftime('%Y-%m-%d')})")

    # Column headers
    c.setFont("Helvetica-Bold", 12)
    y = height - 80
    c.drawString(50, y, "Customer")
    c.drawString(225, y, "Hold Date")
    c.drawString(300, y, "Text")
    y -= 20

    # Draw a line under headers
    c.line(50, y + 15, width - 50, y + 15)

    # Initialize page counter
    page_count = 1
    c.setFont("Helvetica", 10)

    for key in holds:
        customer = holds[key]['name']

        hold_date_str = holds[key]['date'].strftime("%Y-%m-%d")
        text = holds[key]['text']

        # Draw customer, date, text
        c.drawString(50, y, customer)
        c.drawString(225, y, hold_date_str)
        c.drawString(300, y, text)
        y -= 15

        # Start new page if necessary
        if y < 50:
            c.showPage()
            page_count += 1
            y = height - 50
            c.setFont("Helvetica", 10)

    # Save PDF
    c.showPage()
    return page_count

def generate_hold_plants_report(c, holds):
    """
    Generates a PDF report listing all PLANTS and TC items that are on hold.
    Uses holds[key]["items"] directly.

    Sections:
      - Plants on Hold (is_plant OR could_be_plant)
      - TC on Hold (is_tc OR could_be_tc)

    Alphabetical order, deduplicated.
    Returns number of pages generated.
    """
    width, height = letter
    margin = 50
    line_height = 16
    page_count = 1  # First page exists immediately
    y = height - margin

    plant_items = set()
    tc_items = set()

    # --- Collect items from holds ---
    for hold in holds.values():
        for item in hold.get("items", []):
            title = item.get("title", "")

            if is_plant(title) or could_be_plant(title):
                plant_items.add(title)

            if is_tc(title) or could_be_tc(title):
                tc_items.add(title)

    plant_items = sorted(plant_items, key=str.lower)
    tc_items = sorted(tc_items, key=str.lower)

    def draw_report_title():
        """Draw the main report title at the top of the page."""
        nonlocal y
        c.setFont("Helvetica-Bold", 16)
        c.drawString(
            margin,
            y,
            f"Hold Items Report (as of {date.today().strftime('%Y-%m-%d')})"
        )
        y -= 2 * line_height

    def new_page(section_title=None):
        """Start a new page and redraw the report title and optional section title."""
        nonlocal y, page_count
        c.showPage()
        page_count += 1
        y = height - margin
        draw_report_title()
        if section_title:
            c.setFont("Helvetica-Bold", 14)
            c.drawString(margin, y, section_title)
            y -= line_height
            c.setFont("Helvetica", 10)

    # --- Draw title on first page ---
    draw_report_title()

    # --- Plants section ---
    c.setFont("Helvetica-Bold", 14)
    c.drawString(margin, y, "Plants on Hold")
    y -= line_height
    c.setFont("Helvetica", 10)

    if not plant_items:
        c.drawString(margin, y, "None")
        y -= line_height
    else:
        for plant in plant_items:
            if y < margin + line_height:
                new_page("Plants on Hold (cont'd)")
            c.drawString(margin, y, plant)
            y -= line_height

    # --- Space between sections ---
    y -= line_height

    # --- TC section ---
    if y < margin + 4 * line_height:
        new_page("TC on Hold")
    else:
        c.setFont("Helvetica-Bold", 14)
        c.drawString(margin, y, "TC on Hold")
        y -= line_height
        c.setFont("Helvetica", 10)

    if not tc_items:
        c.drawString(margin, y, "None")
        y -= line_height
    else:
        for tc in tc_items:
            if y < margin + line_height:
                new_page("TC on Hold (cont'd)")
            c.drawString(margin, y, tc)
            y -= line_height

    # --- Done ---
    c.showPage()
    return page_count


def generate_conflicts_report(c, conflicts, max_width=470):
    """
    Draws a report listing username/address conflicts, with wrapping for long lines.
    The first part (username or address) is drawn in italics.
    Returns the number of pages created.
    """
    width, height = letter
    line_h = 16

    def draw_wrapped_italic_text(x, y, full_text, font_name="Helvetica", font_size=10):
        """
        Draws text that wraps if it exceeds max_width.
        The first part (before '→') is italic.
        Returns the new y-coordinate after drawing.
        """
        # Split into first part and rest
        if "→" in full_text:
            first_part, rest = full_text.split("→", 1)
            first_part = first_part.strip()
            rest = "→" + rest.strip()
        else:
            first_part = full_text
            rest = ""

        # Draw first part in italics
        first_width = pdfmetrics.stringWidth(first_part, font_name + "-Oblique", font_size)
        if first_width > max_width:
            # Split first_part into words to wrap
            words = first_part.split()
            current_line = ""
            for word in words:
                test_line = current_line + (" " if current_line else "") + word
                test_width = pdfmetrics.stringWidth(test_line, font_name + "-Oblique", font_size)
                if test_width <= max_width:
                    current_line = test_line
                else:
                    c.setFont(font_name + "-Oblique", font_size)
                    c.drawString(x, y, current_line)
                    y -= line_h
                    current_line = word
            if current_line:
                c.setFont(font_name + "-Oblique", font_size)
                c.drawString(x, y, current_line)
                y -= line_h
            first_part_width = 0
        else:
            c.setFont(font_name + "-Oblique", font_size)
            c.drawString(x, y, first_part)
            first_part_width = first_width
            y -= 0  # same line

        # Draw rest normally with wrapping
        words = rest.split()
        current_line = ""
        for word in words:
            test_line = current_line + (" " if current_line else "") + word
            test_width = pdfmetrics.stringWidth(test_line, font_name, font_size)
            if test_width + first_part_width <= max_width:
                current_line = test_line
            else:
                c.setFont(font_name, font_size)
                c.drawString(x + (first_part_width if first_part_width else 0), y, current_line)
                y -= line_h
                current_line = word
                first_part_width = 0  # only apply first part width to first line
        if current_line:
            c.setFont(font_name, font_size)
            c.drawString(x + (first_part_width if first_part_width else 0), y, current_line)
            y -= line_h

        return y

    page_count = 1
    y = height - 50

    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "Username / Address Change Report")
    y -= 30

    # --- Address conflicts ---
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Addresses used by multiple usernames:")
    y -= line_h

    if conflicts.get("address_conflicts"):
        for address, users in conflicts["address_conflicts"].items():
            line_text = f"{address} → {', '.join(users)}"
            if y < 50:
                c.showPage()
                page_count += 1
                y = height - 50
            y = draw_wrapped_italic_text(70, y, line_text)
    else:
        y = draw_wrapped_italic_text(70, y, "None detected")

    y -= 20

    # --- Username conflicts ---
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Usernames linked to multiple addresses:")
    y -= line_h

    if conflicts.get("username_conflicts"):
        for user, addresses in conflicts["username_conflicts"].items():
            line_text = f"{user} → {', '.join(addresses)}"
            if y < 50:
                c.showPage()
                page_count += 1
                y = height - 50
            y = draw_wrapped_italic_text(70, y, line_text)
    else:
        y = draw_wrapped_italic_text(70, y, "None detected")

    c.showPage()
    return page_count