from pathlib import Path
from reportlab.lib.pagesizes import letter
from generate_pages import generate_pick_sheet, generate_order_summary, generate_customer_summary, generate_holds_report, generate_conflicts_report
from numbered_canvas import NumberedCanvas
from order_utils import excel_to_dicts, group_data, sort_grouped_data, get_date_range, aggregate_data
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# ===================================================================
#                           PROCESSING FUNCTIONS
# ===================================================================

def generate_pages(c, sorted_grouped_data, aggregated_data, plants, holds, max_date, conflicts, blocked=False, final_uid=0, progress_callback=None, cancel_event=None):
    groups = []
    single_item_orders = []
    pick_sheet_index = 1

    # Include all orders in total for progress calculation
    total_orders = len(sorted_grouped_data)
    total_orders = max(total_orders, 1)  # avoid division by zero

    groups.append(generate_order_summary(c, aggregated_data, plants, max_date))

    for key in sorted_grouped_data:
        if cancel_event and cancel_event.is_set():
            print("PDF generation cancelled.")
            return groups

        if progress_callback:
            progress_callback((pick_sheet_index / total_orders) * 100, key)

        order = sorted_grouped_data[key]

        if key in holds:
            # Still count toward progress but skip actual page generation
            pick_sheet_index += 1
            continue

        if len(order["items"]) == 1 and order["items"][0]["quantity"] == 1 and order["uid"] > final_uid:
            single_item_orders.append(order)
            pick_sheet_index += 1
            continue

        print(f"Generating pick sheet for {key} ({pick_sheet_index}/{total_orders})")
        groups.append(generate_pick_sheet(c, order, blocked))
        c.showPage()
        pick_sheet_index += 1

    # Add single-item orders and holds reports
    groups.append(generate_customer_summary(c, single_item_orders, max_date))
    groups.append(generate_holds_report(c, holds))
    groups.append(generate_conflicts_report(c, conflicts))

    # Final callback at 100%
    if progress_callback:
        progress_callback(100, "Done")

    return groups

def run_processing(file1, file2=None, progress_callback=None):
    """Runs your existing logic. file2 may be None."""
    file1 = Path(file1)
    file2 = Path(file2) if file2 else None

    if file2 is None:
        # ---------------- SINGLE FILE MODE ----------------
        data = excel_to_dicts(file1)
        grouped_data, conflicts = group_data(data)
        _, max_date = get_date_range(grouped_data)
        formatted = max_date.strftime("%A_%m-%d-%y")
        sorted_grouped_data = sort_grouped_data(grouped_data)
        aggregated_data, plants, holds = aggregate_data(sorted_grouped_data)

        filename = f"{formatted}.pdf"
        c = NumberedCanvas(filename, pagesize=letter)
        c.set_groups(generate_pages(c, sorted_grouped_data, aggregated_data, plants, holds, max_date, conflicts, progress_callback=progress_callback))
        c.save()

    else:
        # ---------------- TWO FILE MODE ----------------
        datas = []
        for file in [file1, file2]:
            grouped_data, _ = group_data(excel_to_dicts(file))
            _, max_date = get_date_range(grouped_data)
            datas.append({"grouped_data": grouped_data, "date": max_date})

        # only use for conflicts initialization
        _, conflicts = group_data(excel_to_dicts(file1) + excel_to_dicts(file2))  # initialize conflicts

        datas.sort(key=lambda item: item["date"], reverse=True)

        grouped_data0 = datas[1]["grouped_data"]
        grouped_data1 = datas[0]["grouped_data"]
        max_date0 = datas[1]["date"]
        max_date1 = datas[0]["date"]

        if max_date0 >= min(get_date_range(grouped_data1)):
            raise ValueError("Date ranges of the two files overlap.")

        sorted_grouped_data0 = sort_grouped_data(grouped_data0)
        sorted_grouped_data1 = sort_grouped_data(grouped_data1)

        i = 1
        for key in sorted_grouped_data1:
            if key in sorted_grouped_data0:
                num_items = 0
                sorted_grouped_data1[key]['uid'] = sorted_grouped_data0[key]['uid']
                for item in sorted_grouped_data0[key]['items'] + sorted_grouped_data1[key]['items']:
                    num_items += item.get('quantity', 1)
                sorted_grouped_data1[key]['num_items'] = num_items
            else:
                sorted_grouped_data1[key]['uid'] = len(sorted_grouped_data0) + i
                i += 1

        sorted_grouped_data = dict(sorted(sorted_grouped_data1.items(), key=lambda x: x[1].get('uid', 0)))
        aggregated_data, plants, holds = aggregate_data(sorted_grouped_data)

        formatted = max_date1.strftime("%A_%m-%d-%y")
        filename = f"{formatted}.pdf"

        c = NumberedCanvas(filename, pagesize=letter)
        c.set_groups(generate_pages(c, sorted_grouped_data, aggregated_data, plants, holds, max_date1, conflicts, True, len(sorted_grouped_data0), progress_callback=progress_callback))
        c.save()

    os.system(f'open "{filename}"')
    return filename

# ===================================================================
#                           TKINTER UI
# ===================================================================

def run_gui():
    if getattr(sys, 'frozen', False):
        current_dir = Path(sys.executable).parent
    else:
        current_dir = Path('.')

    root = tk.Tk()
    root.title("Excel PDF Generator")
    root.geometry("650x400")

    selected_file1 = tk.StringVar()
    selected_file2 = tk.StringVar()

    # Upload file #1
    def upload_file1():
        file_path = filedialog.askopenfilename(
            title="Select Excel File",
            initialdir=str(current_dir),
            filetypes=[("Excel Files", "*.xls *.xlsx")]
        )
        if file_path:
            selected_file1.set(file_path)
            file1_label.config(text=f"File 1 Selected: {file_path}")

    upload1_btn = tk.Button(root, text="Select First Excel File (email ready to ship from mobile device)", command=upload_file1)
    upload1_btn.pack(pady=5)

    file1_label = tk.Label(root, text="No file selected")
    file1_label.pack()

    # Upload file #2 (optional)
    def upload_file2():
        file_path = filedialog.askopenfilename(
            title="Select Excel File",
            initialdir=str(current_dir),
            filetypes=[("Excel Files", "*.xls *.xlsx")]
        )
        if file_path:
            selected_file2.set(file_path)
            file2_label.config(text=f"File 2 Selected: {file_path}")

    upload2_btn = tk.Button(root, text="Select Second Excel File (Optional, download today's sales from computer)", command=upload_file2)
    upload2_btn.pack(pady=5)

    file2_label = tk.Label(root, text="No second file selected")
    file2_label.pack()

    # Progress bar and label
    progress_var = tk.DoubleVar()
    progress_bar = ttk.Progressbar(root, variable=progress_var, maximum=100)
    progress_bar.pack(fill='x', padx=20, pady=10)

    progress_label = tk.Label(root, text="")
    progress_label.pack()

    # Run button
    def update_progress(value, key):
        progress_var.set(value)
        progress_label.config(text=f"Processing: {key}")
        root.update_idletasks()

    def on_run():
        file1 = selected_file1.get().strip()
        file2 = selected_file2.get().strip() or None

        if not file1:
            messagebox.showerror("Error", "Please select the first Excel file.")
            return

        try:
            output = run_processing(file1, file2, progress_callback=update_progress)
            progress_var.set(100)
            progress_label.config(text="Done!")
            messagebox.showinfo("Success", f"PDF created:\n{output}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    tk.Button(root, text="Generate PDF", command=on_run).pack(pady=20)

    root.mainloop()

# ===================================================================
# Launch UI
# ===================================================================

if __name__ == "__main__":
    run_gui()
