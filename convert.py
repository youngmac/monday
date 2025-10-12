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

def generate_packing_slip(c, customer_data):
    from datetime import datetime

    width, height = letter
    margin = 50
    y_start = height - margin

    # Title
    c.setFont("Helvetica-Bold", 20)
    c.drawString(margin, y_start, f"Packing Slip for {customer_data['name']}")

    # Address
    c.setFont("Helvetica", 14)
    y_start -= 30
    c.drawString(margin, y_start, f"Username: {customer_data['username']}")
    y_start -= 20
    c.drawString(margin, y_start, f"Address: {customer_data['address']}")

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
        y_start -= 20
        if min_date == max_date:
            c.drawString(margin, y_start, f"Order Date: {min_date}")
        else:
            c.drawString(margin, y_start, f"Order Dates: {min_date} to {max_date}")

    # Table headers
    y_start -= 40
    c.setFont("Helvetica-Bold", 14)
    c.drawString(margin, y_start, "Qty")
    c.drawString(margin + 50, y_start, "Item")

    # Line under headers
    y_start -= 5
    c.setStrokeColor(colors.black)
    c.line(margin, y_start, width - margin, y_start)

    # Items
    y_start -= 20
    c.setFont("Helvetica", 14)
    for item in customer_data['items']:
        qty = item['quantity']
        title = item['title']

        c.drawString(margin, y_start, str(qty))
        c.drawString(margin + 50, y_start, title)
        y_start -= 5
        c.line(margin, y_start, width - margin, y_start)
        y_start -= 20

        if y_start < margin + 50:
            c.showPage()
            y_start = height - margin

    
# GUI
def main():
    root = tk.Tk()
    root.title("File Upload & Process")
    root.geometry("850x450")

    selected_file = tk.StringVar()

    def upload_file():
        file_path = filedialog.askopenfilename()
        if file_path:
            selected_file.set(file_path)
            file_label.config(text=f"Selected: {file_path}")

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

        return dict(items)

    def run_function():
        file_path = selected_file.get()
        if file_path:
            try:
                data = excel_to_dicts(Path(file_path))
                grouped_data = group_data(data)
                sorted_grouped_data = sort_grouped_data(grouped_data)

                # TODO CHANGE NAME TO DATE 
                # Generate PDFs
                filename = f"{file_path}_output.pdf"
                c = canvas.Canvas(filename, pagesize=letter)
                for key in sorted_grouped_data:
                    generate_packing_slip(c, sorted_grouped_data[key])
                    c.showPage()
                c.save()

                messagebox.showinfo("Success", f"PDF created: {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"An error occurred:\n{e}")
        else:
            messagebox.showwarning("No file", "Please upload a file first.")

    # GUI Layout
    upload_btn = tk.Button(root, text="Upload file", command=upload_file)
    upload_btn.pack(pady=10)

    file_label = tk.Label(root, text="No file selected")
    file_label.pack(pady=5)

    process_btn = tk.Button(root, text="Create PDF in folder", command=run_function)
    process_btn.pack(pady=20)

    root.mainloop()


if __name__ == "__main__":
    main()