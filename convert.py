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
import sys

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
            self.drawRightString(7.75 * inch, .75 * inch, f"Page {self._pageNumber} of {page_count}")
        else:
            i = self._pageNumber
            group_index = 0
            while i > self.groups[group_index]:
                i -= self.groups[group_index]
                group_index += 1   
            self.drawRightString(7.75 * inch, .75 * inch, f"Page {i} of {self.groups[group_index]}")



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
    return (row.get("Recipient Name") or "").lower().strip() + "_" \
        + (row.get("Street Line 1") or "").lower().strip() + "_" \
        + (row.get("Street Line 2") or "").lower().strip() + "_" \
        + (row.get("State") or "").lower().strip() + "_" \
        + (row.get("Country") or "").lower().strip() + "_" \
        + (row.get("Zip/Postal Code") or "").lower().strip()

# assume USD, no variant/sku
def group_data(data):
    grouped_data = {}
    for row in data:
        key = name_address_to_key(row)
        if key not in grouped_data:
            grouped_data[key] = {
                "name": (row.get("Recipient Name") or ""),
                "username": (row.get("Palmstreet UserName") or ""),
                "address": (row.get("Street Line 1") or "") + ", "  \
                    + ((row.get("Street Line 2") or "") + ", " if (row.get("Street Line 2") or "") != "" else "") \
                    + (row.get("City") or "") + ", " \
                    + (row.get("State") or "") + " " \
                    + (row.get("Zip/Postal Code") or ""),
                "items": [{
                            "title": (row.get("Item Title") or ""),
                            "price": (row.get("Item Price") or 0),
                            "quantity": (row.get("Quantity") or 0),
                            "time": (row.get("Order Date(PDT)") or ""),
                        }],
            }
        else:
            grouped_data[key]["items"].append({
                            "title": (row.get("Item Title") or ""),
                            "price": (row.get("Item Price") or 0),
                            "quantity": (row.get("Quantity") or 0),
                            "time": (row.get("Order Date(PDT)") or ""),
                        })
    return grouped_data

def get_date_range(grouped_data):
    min_date = None
    max_date = None
    for key in grouped_data:
        for item in grouped_data[key]['items']:
            try:
                dt = datetime.strptime(str(item['time']), "%Y-%m-%d %H:%M:%S")
                if min_date is None or dt < min_date:
                    min_date = dt
                if max_date is None or dt > max_date:
                    max_date = dt
            except:
                continue
    return min_date, max_date

def sort_grouped_data(grouped_data):
        def item_count(items):
            return len(items)

        def earliest_date(items):
            dates = []
            for item in items:
                try:
                    dates.append(datetime.strptime(str(item['time']), '%Y-%m-%d %H:%M:%S'))
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

def generate_packing_slip(c, customer_data, boxed=False):
    num_pages = 1
    width, height = letter
    margin = 30
    y_start = height - margin - 30

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
        c.drawString(width - margin - uid_width, y_start - 65, uid_text)
        if (boxed):
            x = width - margin - uid_width
            y = y_start - 70
            padding = 5
            text_height = 100 
            c.setLineWidth(5)  # This sets the thickness of the rectangle's border
            c.rect(x - padding, y - padding, uid_width + 2 * padding, text_height - 10, stroke=1, fill=0)
            c.setLineWidth(1)  # Reset to default line width

        # Address
        y_start -= 25
        c.setFont("Helvetica", 14)
        c.drawString(margin, y_start, customer_data['address'])

        # Order Date Range
        def get_order_date_range(items):
            dates = []
            for item in items:
                try:
                    dt = datetime.strptime(str(item['time']), "%Y-%m-%d %H:%M:%S")
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
                
        y_start -= 10

        # Table headers
        y_start -= 20
        c.setFont("Helvetica-Bold", 14)
        c.setStrokeColor(colors.black)
        c.line(margin, y_start, width - margin, y_start)

        y_start -= 17

    def draw_footer():
        nonlocal num_items
        c.setFont("Helvetica-Bold", 40)
        total = ""
        if ('num_items' in customer_data): # merged order total
            total = str(customer_data['num_items'])
        else: # not merged, count
            total = str(len(customer_data['items']))
        total_items_width = c.stringWidth(total, "Helvetica-Bold", 40)
        text_height = 40
        x, y = margin, margin + 20
        c.drawString(x, y, total)

        if boxed:
            c.setLineWidth(3)
            c.rect(x - 5, y - 5, total_items_width + 10, text_height, stroke=1, fill=0)
            c.setLineWidth(1)  # Reset to default line width

        c.setFont("Helvetica", 10)
        c.drawString(x + total_items_width + 8 if boxed else x + total_items_width, y, " " + str(num_items))

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

        if y_start < margin + 60:
            draw_footer()
            c.showPage()
            num_pages += 1
            num_items = 0
            y_start = height - margin - 30
            draw_header()
    draw_footer()

    return num_pages

    
# GUI
def main():
    current_dir = None

    if getattr(sys, 'frozen', False):
        # Running from a bundled .exe (like PyInstaller)
        current_dir = Path(os.path.dirname(sys.executable))
    else:
        # Running from a .py file
        current_dir = Path('.')

    # Get all Excel files (.xlsx and .xls)
    excel_files = list(current_dir.glob("*.xlsx")) + list(current_dir.glob("*.xls"))

    if len(excel_files) == 0 or len(excel_files) > 2:
        print("No Excel files found in the current directory.")
        return
    
    elif len(excel_files) == 1:
        data = excel_to_dicts(Path(excel_files[0]))
        grouped_data = group_data(data)
        min_date, max_date = get_date_range(grouped_data)
        formatted = max_date.strftime("%A_%m-%d-%y")
        sorted_grouped_data = sort_grouped_data(grouped_data)

        # Generate PDFs
        groups = []
        filename = f"{formatted}.pdf"
        c = NumberedCanvas(filename, pagesize=letter)
        for key in sorted_grouped_data:
            groups.append(generate_packing_slip(c, sorted_grouped_data[key]))
            c.showPage()
        c.set_groups(groups)
        c.save()

    else: # len == 2
        data0 = excel_to_dicts(Path(excel_files[0]))
        data1 = excel_to_dicts(Path(excel_files[1]))
        grouped_data0 = group_data(data0)
        grouped_data1 = group_data(data1)
        min_date0, max_date0 = get_date_range(grouped_data0)
        min_date1, max_date1 = get_date_range(grouped_data1)
        # switch if out of order
        if max_date0 > max_date1:
            data0, data1 = data1, data0
            grouped_data0, grouped_data1 = grouped_data1, grouped_data0
            min_date0, max_date0, min_date1, max_date1 = min_date1, max_date1, min_date0, max_date0

        if max_date0 > min_date1:
            print("Error: Date ranges of the two files overlap.")
            return
        
        sorted_grouped_data0 = sort_grouped_data(grouped_data0)
        sorted_grouped_data1 = sort_grouped_data(grouped_data1)

        i = 1
        for key in sorted_grouped_data1:
            if key in sorted_grouped_data0:
                sorted_grouped_data1[key]['uid'] = sorted_grouped_data0[key]['uid']
            else: # assign new uid
                sorted_grouped_data1[key]['uid'] = len(sorted_grouped_data0) + i
                i += 1
            if key in sorted_grouped_data0:
                sorted_grouped_data1[key]['num_items'] = len(sorted_grouped_data0[key]['items']) + len(sorted_grouped_data1[key]['items'])

        sorted_grouped_data = dict(sorted(sorted_grouped_data1.items(), key=lambda x: x[1].get('uid', 0)))
        formatted = max_date1.strftime("%A_%m-%d-%y")

        # Generate PDFs
        groups = []
        filename = f"{formatted}.pdf"
        c = NumberedCanvas(filename, pagesize=letter)
        for key in sorted_grouped_data:
            groups.append(generate_packing_slip(c, sorted_grouped_data[key], True))
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