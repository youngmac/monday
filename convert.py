from openpyxl import load_workbook
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib import colors
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
from datetime import datetime
import os
import platform
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self.pages = []
        self.groups = []

    def showPage(self):
        # Save the drawing commands for the current page
        self.pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        """Add page info to each page (page x of y) and save."""
        page_count = len(self.pages)
        for page in self.pages:
            # From ChatGPT: When you call self.__dict__.update(page), you are replacing the current 
            # canvas object's internal state with the saved state from that page. Essentially, you're 
            # restoring the canvas to how it was when that page was being created.
            # So store a temp and reload after updating
            temp_groups = self.groups
            self.__dict__.update(page)
            self.groups = temp_groups
            self.draw_page_number(page_count)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)
    
    def set_groups(self, groups):
        self.groups = groups

    def draw_page_number(self, page_count):
        self.setFont("Helvetica", 16)
        if self.groups == [] or sum(self.groups) != page_count:
            self.drawRightString(8 * inch, .5 * inch, f"Page {self._pageNumber} of {page_count}")
        else:
            i = self._pageNumber
            group_index = 0
            while i > self.groups[group_index]:
                i -= self.groups[group_index]
                group_index += 1   
            self.drawRightString(8 * inch, .5 * inch, f"Page {i} of {self.groups[group_index]}")



def excel_to_dicts(file_path):
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    wb = load_workbook(filename=file_path, data_only=True)

    sheet = wb.active
    headers = [cell.value for cell in sheet[1]]

    # Read the data rows into a list of dictionaries
    data = []
    for row in sheet.iter_rows(min_row=2, values_only=True):
        row_dict = dict(zip(headers, row))
        data.append(row_dict)

    return data

# Does not handle mispellings/mistakes/abbreviations vs full words
def name_address_to_key(row):
    return row.get("Recipient Name", "").lower().strip() + "_" \
        + row.get("Street Line 1", "").lower().strip() + "_" \
        + row.get("Street Line 2", "").lower().strip() + "_" \
        + row.get("State", "").lower().strip() + "_" \
        + row.get("Country", "").lower().strip() + "_" \
        + row.get("Zip/Postal Code", "").lower().strip()

# assume USD, no variant/sku
def group_data(data):
    grouped_data = {}
    for row in data:
        key = name_address_to_key(row)
        if key not in grouped_data:
            grouped_data[key] = {
                "name": row.get("Recipient Name", ""),
                "username": row.get("Palmstreet UserName", ""),
                "address": row.get("Street Line 1", "") + ", "  \
                    + (row.get("Street Line 2", "") + ", " if row.get("Street Line 2", "") != "" else "") \
                    + row.get("City", "") + ", " \
                    + row.get("State", "") + " " \
                    + row.get("Zip/Postal Code", ""),
                "items": [{
                            "title": row.get("Item Title", ""),
                            "price": row.get("Item Price", 0),
                            "quantity": row.get("Quantity", 0),
                            "time": row.get("Order Date(PDT)", ""),
                        }],
            }
        else:
            grouped_data[key]["items"].append({
                            "title": row.get("Item Title", ""),
                            "price": row.get("Item Price", 0),
                            "quantity": row.get("Quantity", 0),
                            "time": row.get("Order Date(PDT)", ""),
                        })
    return grouped_data

def sort_grouped_data(grouped_data):
        def item_count(items):
            return len(items)

        def earliest_date(items):
            dates = []
            for item in items:
                try:
                    dates.append(datetime.strptime(item['time'], '%Y-%m-%d %H:%M:%S'))
                except:
                    continue
            return min(dates) if dates else datetime.max

        def get_sort_key_func(key):
            if key == "Name":
                return lambda x: x[1]["name"].lower()
            elif key == "Username":
                return lambda x: x[1]["username"].lower()
            elif key == "Size":
                return lambda x: item_count(x[1]["items"])
            elif key == "Earliest Order Date":
                return lambda x: earliest_date(x[1]["items"])
            else:
                return None

        items = list(grouped_data.items())

        # Apply sorting from lowest to highest priority (reversed)
        for key, order in reversed(list(zip(["Size", "Name"], [ "Descending", "Ascending"]))):
            key_func = get_sort_key_func(key)
            if key_func:
                reverse = order == "Descending"
                items.sort(key=key_func, reverse=reverse)

        # Add uid
        for i, (key, value) in enumerate(items):
            value["uid"] = i + 1

        return dict(items)

def generate_packing_slip(c, customer_data):
    num_pages = 1
    width, height = letter
    margin = 40
    y_start = height - margin - 10 # slight adjustment for top margin

    def draw_header():
        nonlocal y_start
        # username/Name
        c.setFont("Helvetica-Bold", 20)
        c.drawString(margin, y_start, customer_data['username'] + " ")

        c.setFont("Helvetica", 14)
        username_width = c.stringWidth(customer_data['username'] + " ", "Helvetica-Bold", 20)
        c.drawString(margin + username_width, y_start, f"{customer_data['name']}")

        # UID on the right
        c.setFont("Helvetica", 100)
        uid_text = "{:03}".format(customer_data.get('uid', ''))
        uid_width = c.stringWidth(uid_text, "Helvetica", 100)
        c.drawString(width - margin - uid_width, y_start - 55, uid_text)

        # Address
        y_start -= 25
        c.setFont("Helvetica", 14)
        c.drawString(margin, y_start, customer_data['address'])

        # Order Date Range
        def get_order_date_range(items):
            dates = []
            for item in items:
                try:
                    dt = datetime.strptime(item['time'], "%Y-%m-%d %H:%M:%S")
                    dates.append(dt)
                except:
                    continue
            if dates:
                return min(dates).date(), max(dates).date()
            return None, None

        min_date, max_date = get_order_date_range(customer_data['items'])
        if min_date and max_date:
            y_start -= 25
            max_dow_str = max_date.strftime("%A")
            max_date_str = max_date.strftime(", %b %d")
            min_date_str = min_date.strftime("%A, %b %d")

            c.setFont("Helvetica-Bold", 18)
            c.drawString(margin, y_start, max_dow_str)

            cur_width = c.stringWidth(max_dow_str, "Helvetica-Bold", 18)
            c.setFont("Helvetica", 14)
            c.drawString(margin + cur_width, y_start, max_date_str)

            if min_date != max_date:
                cur_width += c.stringWidth(max_date_str, "Helvetica", 14)
                c.drawString(margin + cur_width, y_start, " to ")
                cur_width += c.stringWidth(" to ", "Helvetica", 14)
                c.drawString(margin + cur_width, y_start, min_date_str)

        # Table headers
        y_start -= 20
        c.setFont("Helvetica-Bold", 14)
        c.setStrokeColor(colors.black)
        c.line(margin, y_start, width - margin, y_start)

        y_start -= 17

    def draw_footer():
        nonlocal num_items
        c.setFont("Helvetica-Bold", 40)
        c.drawString(margin, margin, str(len(customer_data['items'])))
        total_items_width = c.stringWidth(str(len(customer_data['items'])), "Helvetica-Bold", 40)
        c.setFont("Helvetica", 10)
        c.drawString(margin + total_items_width, margin, " " + str(num_items))

    draw_header()
    num_items = 0

    for item in customer_data['items']:
        c.setFont("Helvetica", 14)
        title = item['title']
        c.rect(margin, y_start - 1, 12, 12, stroke=1, fill=0)
        c.drawString(margin + 20 , y_start, title)
        num_items += 1
        y_start -= 7
        c.line(margin, y_start, width - margin, y_start)
        y_start -= 17

        if y_start < margin + 50:
            draw_footer()
            c.showPage()
            num_pages += 1
            num_items = 0
            y_start = height - margin - 10
            draw_header()
    draw_footer()

    return num_pages

    
# GUI
def main():
    selected_file = "Youngauctioneertoo_1760301513876_default.xlsx"

    data = excel_to_dicts(Path(selected_file))
    grouped_data = group_data(data)
    sorted_grouped_data = sort_grouped_data(grouped_data)

    # Generate PDFs
    groups = []
    filename = f"{selected_file}_output.pdf"
    c = NumberedCanvas(filename, pagesize=letter)
    for key in sorted_grouped_data:
        groups.append(generate_packing_slip(c, sorted_grouped_data[key]))
        c.showPage()
    c.set_groups(groups)
    c.save()
    print(f"PDF created: {filename}")

    # Open the generated PDF file
    os.system(f'open "{filename}"')
    # root = tk.Tk()
    # root.title("File Upload & Process")
    # root.geometry("850x450")

    # selected_file = tk.StringVar()

    # def upload_file():
    #     file_path = filedialog.askopenfilename()
    #     if file_path:
    #         selected_file.set(file_path)
    #         file_label.config(text=f"Selected: {file_path}")

    # def sort_grouped_data(grouped_data):
    #     def item_count(items):
    #         return len(items)

    #     def earliest_date(items):
    #         dates = []
    #         for item in items:
    #             try:
    #                 dates.append(datetime.strptime(item['time'], '%Y-%m-%d %H:%M:%S'))
    #             except:
    #                 continue
    #         return min(dates) if dates else datetime.max

    #     def get_sort_key_func(key):
    #         if key == "Name":
    #             return lambda x: x[1]["name"].lower()
    #         elif key == "Username":
    #             return lambda x: x[1]["username"].lower()
    #         elif key == "Size":
    #             return lambda x: item_count(x[1]["items"])
    #         elif key == "Earliest Order Date":
    #             return lambda x: earliest_date(x[1]["items"])
    #         else:
    #             return None

    #     items = list(grouped_data.items())

    #     # Apply sorting from lowest to highest priority (reversed)
    #     for key, order in reversed(list(zip(["Size", "Name"], [ "Descending", "Ascending"]))):
    #         key_func = get_sort_key_func(key)
    #         if key_func:
    #             reverse = order == "Descending"
    #             items.sort(key=key_func, reverse=reverse)

    #     return dict(items)

    # def run_function():
    #     file_path = selected_file.get()
    #     if file_path:
    #         try:
    #             data = excel_to_dicts(Path(file_path))
    #             grouped_data = group_data(data)
    #             sorted_grouped_data = sort_grouped_data(grouped_data)

    #             # TODO CHANGE NAME TO DATE 
    #             # Generate PDFs
    #             filename = f"{file_path}_output.pdf"
    #             c = canvas.Canvas(filename, pagesize=letter)
    #             for key in sorted_grouped_data:
    #                 generate_packing_slip(c, sorted_grouped_data[key])
    #                 c.showPage()
    #             c.save()

    #             messagebox.showinfo("Success", f"PDF created: {filename}")
    #         except Exception as e:
    #             messagebox.showerror("Error", f"An error occurred:\n{e}")
    #     else:
    #         messagebox.showwarning("No file", "Please upload a file first.")

    # # GUI Layout
    # upload_btn = tk.Button(root, text="Upload file", command=upload_file)
    # upload_btn.pack(pady=10)

    # file_label = tk.Label(root, text="No file selected")
    # file_label.pack(pady=5)

    # process_btn = tk.Button(root, text="Create PDF in folder", command=run_function)
    # process_btn.pack(pady=20)

    # root.mainloop()


if __name__ == "__main__":
    main()