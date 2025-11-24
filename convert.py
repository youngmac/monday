from pathlib import Path
from reportlab.lib.pagesizes import letter
from generate_pages import generate_pick_sheet, generate_order_summary, generate_customer_summary, generate_holds_report
from numbered_canvas import NumberedCanvas
from order_utils import excel_to_dicts, group_data, sort_grouped_data, get_date_range, aggregate_data
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
import sys, os

def generate_pages(c, sorted_grouped_data, aggregated_data, plants, holds, max_date, blocked=False, final_uid=0):
    groups = []
    single_item_orders = []
    pick_sheet_index = 1

    groups.append(generate_order_summary(c, aggregated_data, plants, max_date))

    num_singles = 0

    for key in sorted_grouped_data:
        if len(sorted_grouped_data[key]["items"]) == 1:
            num_singles += 1

    for key in sorted_grouped_data:
        if key in holds:
            continue  # skip orders with holds

        if len(sorted_grouped_data[key]["items"]) == 1 and sorted_grouped_data[key]["uid"] > final_uid:
            single_item_orders.append(sorted_grouped_data[key])
            continue

        print(f"Generating pick sheet (weather) for {key} ..." + str(pick_sheet_index) + "/" + str(len(sorted_grouped_data) - num_singles))
        pick_sheet_index += 1
        groups.append(generate_pick_sheet(c, sorted_grouped_data[key], blocked))           
        c.showPage()

    groups.append(generate_customer_summary(c, single_item_orders, max_date))
    groups.append(generate_holds_report(c, holds))
    return groups

def run_processing(file1, file2=None):
    """Runs your existing logic. file2 may be None."""
    # Convert to Path objects
    file1 = Path(file1)
    file2 = Path(file2) if file2 else None

    if file2 is None:
        # ---------------- SINGLE FILE MODE ----------------
        data = excel_to_dicts(file1)
        grouped_data = group_data(data)
        _, max_date = get_date_range(grouped_data)
        formatted = max_date.strftime("%A_%m-%d-%y")
        sorted_grouped_data = sort_grouped_data(grouped_data)
        aggregated_data, plants, holds = aggregate_data(sorted_grouped_data)

        filename = f"{formatted}.pdf"
        c = NumberedCanvas(filename, pagesize=letter)
        c.set_groups(generate_pages(c, sorted_grouped_data, aggregated_data, plants, holds, max_date))
        c.save()

    else:
        # ---------------- TWO FILE MODE ----------------
        datas = []
        for file in [file1, file2]:
            grouped_data = group_data(excel_to_dicts(file))
            _, max_date = get_date_range(grouped_data)
            datas.append({"grouped_data": grouped_data, "date": max_date})

        datas.sort(key=lambda item: item["date"], reverse=True)

        grouped_data0 = datas[1]["grouped_data"]
        grouped_data1 = datas[0]["grouped_data"]
        max_date0 = datas[1]["date"]
        max_date1 = datas[0]["date"]

        if max_date0 >= min(get_date_range(grouped_data1)):
            raise ValueError("Date ranges of the two files overlap.")

        sorted_grouped_data0 = sort_grouped_data(grouped_data0)
        sorted_grouped_data1 = sort_grouped_data(grouped_data1)

        # Assign UIDs and merge counts
        i = 1
        for key in sorted_grouped_data1:
            if key in sorted_grouped_data0:
                sorted_grouped_data1[key]['uid'] = sorted_grouped_data0[key]['uid']
                sorted_grouped_data1[key]['num_items'] = len(sorted_grouped_data0[key]['items']) + len(sorted_grouped_data1[key]['items'])
            else:
                sorted_grouped_data1[key]['uid'] = len(sorted_grouped_data0) + i
                i += 1

        sorted_grouped_data = dict(sorted(sorted_grouped_data1.items(), key=lambda x: x[1].get('uid', 0)))
        aggregated_data, plants, holds = aggregate_data(sorted_grouped_data)

        formatted = max_date1.strftime("%A_%m-%d-%y")
        filename = f"{formatted}.pdf"

        c = NumberedCanvas(filename, pagesize=letter)
        c.set_groups(generate_pages(c, sorted_grouped_data, aggregated_data, plants, holds, max_date1, True, len(sorted_grouped_data0)))
        c.save()

    os.system(f'open "{filename}"')
    return filename


# ===================================================================
#                           TKINTER UI
# ===================================================================

def run_gui():
    from tkinter import filedialog

    # Determine working directory (your existing logic)
    if getattr(sys, 'frozen', False):
        current_dir = Path(sys.executable).parent
    else:
        current_dir = Path('.')

    root = tk.Tk()
    root.title("Excel PDF Generator")
    root.geometry("650x300")

    selected_file1 = tk.StringVar()
    selected_file2 = tk.StringVar()

    # ---------------------------------------------------
    # Upload button #1 (REQUIRED)
    # ---------------------------------------------------
    def upload_file1():
        file_path = filedialog.askopenfilename(
            title="Select Excel File",
            initialdir=str(current_dir),                     # macOS Finder starts here
            filetypes=[("Excel Files", "*.xls *.xlsx")]
        )
        if file_path:
            selected_file1.set(file_path)
            file1_label.config(text=f"File 1 Selected: {file_path}")

    upload1_btn = tk.Button(root, text="Select First (Use Ready to ship from mobile device's \"send email\")", command=upload_file1)
    upload1_btn.pack(pady=10)

    file1_label = tk.Label(root, text="No file selected")
    file1_label.pack()

    # ---------------------------------------------------
    # Upload button #2 (OPTIONAL)
    # ---------------------------------------------------
    def upload_file2():
        file_path = filedialog.askopenfilename(
            title="Select Excel File",
            initialdir=str(current_dir),
            filetypes=[("Excel Files", "*.xls *.xlsx")]
        )
        if file_path:
            selected_file2.set(file_path)
            file2_label.config(text=f"File 2 Selected: {file_path}")

    upload2_btn = tk.Button(root, text="Select Second Excel File (optional, export Monday's date from computer)", command=upload_file2)
    upload2_btn.pack(pady=10)

    file2_label = tk.Label(root, text="No second file selected")
    file2_label.pack()

    # ---------------------------------------------------
    # RUN BUTTON
    # ---------------------------------------------------
    def on_run():
        file1 = selected_file1.get().strip()
        file2 = selected_file2.get().strip()

        if not file1:
            messagebox.showerror("Error", "Please select the first Excel file.")
            return

        if not file2:
            file2 = None  # single-file mode

        try:
            output = run_processing(file1, file2)
            messagebox.showinfo("Success", f"PDF created:\n{output}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    tk.Button(root, text="Generate PDF", command=on_run).pack(pady=20)

    root.mainloop()


# ===================================================================
# Launch UI instead of CLI
# ===================================================================

if __name__ == "__main__":
    run_gui()