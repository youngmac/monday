from pathlib import Path
from reportlab.lib.pagesizes import letter
from generate_pages import generate_pick_sheet, generate_order_summary, generate_customer_summary, generate_holds_report, generate_conflicts_report, generate_hold_plants_report
from numbered_canvas import NumberedCanvas
from order_utils import excel_to_dicts, group_data, sort_grouped_data, get_date_range, aggregate_data
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from est_transit_times import ShippingTransitTime

shipping_transit_time = ShippingTransitTime() # global instance for caching

# ===================================================================
#                           PROCESSING FUNCTIONS
# ===================================================================

def generate_pages(c, sorted_grouped_data, aggregated_data, plants, holds, max_date, conflicts, blocked=False, final_uid=0, progress_callback=None, bypass_future_hold=False, double_blocked=False, cancel_event=None):
    groups = []
    single_item_orders = []
    pick_sheet_index = 1

    # Include all orders in total for progress calculation
    total_orders = len(sorted_grouped_data)
    total_orders = max(total_orders, 1)  # avoid division by zero

    groups.append(generate_order_summary(c, aggregated_data, plants, max_date))
    groups.append(generate_conflicts_report(c, conflicts))
    groups.append(generate_holds_report(c, holds))
    groups.append(generate_hold_plants_report(c, holds))
    for key in sorted_grouped_data:
        if cancel_event and cancel_event.is_set():
            print("PDF generation cancelled.")
            return groups

        if progress_callback:
            progress_callback((pick_sheet_index / total_orders) * 100, key)

        order = sorted_grouped_data[key]

        if key in holds and not bypass_future_hold:
            # Still count toward progress but skip actual page generation
            pick_sheet_index += 1
            continue

        if len(order["items"]) == 1 and order["items"][0]["quantity"] == 1 and order["uid"] > final_uid and not blocked and not double_blocked:
            single_item_orders.append(order)
            pick_sheet_index += 1
            continue

        print(f"Generating pick sheet for {key} ({pick_sheet_index}/{total_orders})")
        groups.append(generate_pick_sheet(c, order, blocked, double_blocked))
        c.showPage()
        pick_sheet_index += 1

    # Add single-item orders and holds reports
    groups.append(generate_customer_summary(c, single_item_orders, max_date))

    # Final callback at 100%
    if progress_callback:
        progress_callback(100, "Done")

    return groups

def run_processing(file1, file2=None, file3=None, progress_callback=None, transit_progress_callback=None, bypass_future_hold=False):
    """Runs your existing logic. file2 may be None."""
    bypass_future_hold = bool(bypass_future_hold)
    file1 = Path(file1)
    file2 = Path(file2) if file2 else None
    file3 = Path(file3) if file3 else None

    if file2 is None:
        # ---------------- SINGLE FILE MODE ----------------
        data = excel_to_dicts(file1)
        grouped_data, conflicts = group_data(data, shipping_transit_time, transit_progress_callback)
        _, max_date = get_date_range(grouped_data)
        formatted = max_date.strftime("%A_%m-%d-%y")
        sorted_grouped_data = sort_grouped_data(grouped_data)
        aggregated_data, plants, holds = aggregate_data(sorted_grouped_data)

        filename = f"{formatted}.pdf"
        c = NumberedCanvas(filename, pagesize=letter)
        c.set_groups(generate_pages(
            c, 
            sorted_grouped_data, 
            aggregated_data, 
            plants, 
            holds, 
            max_date, 
            conflicts,
            progress_callback=progress_callback,
            bypass_future_hold=bypass_future_hold
        ))
        c.save()

    elif file2 is not None and file3 is None:
        # ---------------- TWO FILE MODE ----------------
        datas = []
        for file in [file1, file2]:
            grouped_data, _ = group_data(excel_to_dicts(file), shipping_transit_time, transit_progress_callback)
            _, max_date = get_date_range(grouped_data)
            datas.append({"grouped_data": grouped_data, "date": max_date})

        # only use for conflicts initialization
        _, conflicts = group_data(excel_to_dicts(file1) + excel_to_dicts(file2), shipping_transit_time, transit_progress_callback)  # initialize conflicts

        datas.sort(key=lambda item: item["date"], reverse=True)

        grouped_data0 = datas[1]["grouped_data"]
        grouped_data1 = datas[0]["grouped_data"]
        max_date0 = datas[1]["date"]
        max_date1 = datas[0]["date"]

        if max_date0 >= min(get_date_range(grouped_data1)):
            raise ValueError("Date ranges of the two files overlap.")

        sorted_grouped_data0 = sort_grouped_data(grouped_data0)
        sorted_grouped_data1 = sort_grouped_data(grouped_data1)

        # Adjust costs for merge

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
            sorted_grouped_data1[key]['costs']['total_cost'] += sorted_grouped_data0.get(key, {}).get('costs', {}).get('total_cost', 0.0)
            sorted_grouped_data1[key]['costs']['plant_cost'] += sorted_grouped_data0.get(key, {}).get('costs', {}).get('plant_cost', 0.0)
            sorted_grouped_data1[key]['costs']['ship_cost'] += sorted_grouped_data0.get(key, {}).get('costs', {}).get('ship_cost', 0.0)
            sorted_grouped_data1[key]['costs']['subtotal'] += sorted_grouped_data0.get(key, {}).get('costs', {}).get('subtotal', 0.0)
            sorted_grouped_data1[key]['2day'] = sorted_grouped_data1[key]['2day'] or sorted_grouped_data0.get(key, {}).get('2day', False)
            sorted_grouped_data1[key]['1day'] = sorted_grouped_data1[key]['1day'] or sorted_grouped_data0.get(key, {}).get('1day', False)

        sorted_grouped_data = dict(sorted(sorted_grouped_data1.items(), key=lambda x: x[1].get('uid', 0)))
        aggregated_data, plants, holds = aggregate_data(sorted_grouped_data)

        formatted = max_date1.strftime("%A_%m-%d-%y")
        filename = f"{formatted}.pdf"

        c = NumberedCanvas(filename, pagesize=letter)
        c.set_groups(generate_pages(c, sorted_grouped_data, aggregated_data, plants, holds, max_date1, conflicts, True, len(sorted_grouped_data0), progress_callback=progress_callback))
        c.save()
    else: # file3 is not None
         # ---------------- START W TWO FILE MODE ----------------
        datas = []
        for file in [file1, file2]:
            grouped_data, _ = group_data(excel_to_dicts(file), shipping_transit_time, transit_progress_callback)
            _, max_date = get_date_range(grouped_data)
            datas.append({"grouped_data": grouped_data, "date": max_date})

        # only use for conflicts initialization
        _, conflicts = group_data(excel_to_dicts(file1) + excel_to_dicts(file2), shipping_transit_time, transit_progress_callback)  # initialize conflicts

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
            sorted_grouped_data1[key]['costs']['total_cost'] += sorted_grouped_data0.get(key, {}).get('costs', {}).get('total_cost', 0.0)
            sorted_grouped_data1[key]['costs']['plant_cost'] += sorted_grouped_data0.get(key, {}).get('costs', {}).get('plant_cost', 0.0)
            sorted_grouped_data1[key]['costs']['ship_cost'] += sorted_grouped_data0.get(key, {}).get('costs', {}).get('ship_cost', 0.0)
            sorted_grouped_data1[key]['costs']['subtotal'] += sorted_grouped_data0.get(key, {}).get('costs', {}).get('subtotal', 0.0)
            sorted_grouped_data1[key]['2day'] = sorted_grouped_data1[key]['2day'] or sorted_grouped_data0.get(key, {}).get('2day', False)
            sorted_grouped_data1[key]['1day'] = sorted_grouped_data1[key]['1day'] or sorted_grouped_data0.get(key, {}).get('1day', False)

        sorted_grouped_data = dict(sorted(sorted_grouped_data1.items(), key=lambda x: x[1].get('uid', 0)))

        # ---------------- ADD IN THIRD FILE ----------------
        grouped_data3, _ = group_data(excel_to_dicts(file3), shipping_transit_time, transit_progress_callback)
        _, max_date3 = get_date_range(grouped_data3)
        sorted_grouped_data3 = sort_grouped_data(grouped_data3)

        # Merge the third file into the existing data
        j = 1
        for key in sorted_grouped_data3:
            # print(f"Processing third file key: {key}")
            if key in sorted_grouped_data:
                num_items = 0
                sorted_grouped_data3[key]['uid'] = sorted_grouped_data[key]['uid']
                for item in sorted_grouped_data[key]['items'] + sorted_grouped_data3[key]['items']:
                    num_items += item.get('quantity', 1)
                # print(f"if Total items for {key}: {num_items}")
                # print(f"if Assigning existing UID for {key}: {sorted_grouped_data[key]['uid']}")
                sorted_grouped_data3[key]['num_items'] = num_items
            elif key in sorted_grouped_data0:
                num_items = 0
                sorted_grouped_data3[key]['uid'] = sorted_grouped_data0[key]['uid']
                for item in sorted_grouped_data0[key]['items'] + sorted_grouped_data3[key]['items']:
                    num_items += item.get('quantity', 1)
                # print(f"elif Total items for {key}: {num_items}")
                # print(f"elif Assigning existing UID for {key}: {sorted_grouped_data0[key]['uid']}")
                sorted_grouped_data3[key]['num_items'] = num_items
            else:
                # print(f"else Assigning new UID for {key}: {len(sorted_grouped_data) + j}")
                sorted_grouped_data3[key]['uid'] = len(sorted_grouped_data0) + i + j
                j += 1
            sorted_grouped_data3[key]['costs']['total_cost'] += sorted_grouped_data.get(key, {}).get('costs', {}).get('total_cost', 0.0)
            sorted_grouped_data3[key]['costs']['plant_cost'] += sorted_grouped_data.get(key, {}).get('costs', {}).get('plant_cost', 0.0)
            sorted_grouped_data3[key]['costs']['ship_cost'] += sorted_grouped_data.get(key, {}).get('costs', {}).get('ship_cost', 0.0)
            sorted_grouped_data3[key]['costs']['subtotal'] += sorted_grouped_data.get(key, {}).get('costs', {}).get('subtotal', 0.0)
            sorted_grouped_data3[key]['2day'] = sorted_grouped_data3[key]['2day'] or sorted_grouped_data1.get(key, {}).get('2day', False)
            sorted_grouped_data3[key]['1day'] = sorted_grouped_data3[key]['1day'] or sorted_grouped_data1.get(key, {}).get('1day', False)

        # third file's items matched with first two's uids
        merged_grouped_data = dict(sorted(sorted_grouped_data3.items(), key=lambda x: x[1].get('uid', 0)))

        aggregated_data, plants, holds = aggregate_data(merged_grouped_data)

        formatted = max_date3.strftime("%A_%m-%d-%y")
        filename = f"{formatted}.pdf"

        c = NumberedCanvas(filename, pagesize=letter)
        c.set_groups(generate_pages(c, merged_grouped_data, aggregated_data, plants, holds, max_date3, conflicts, True, len(merged_grouped_data), progress_callback=progress_callback, double_blocked=True))
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
    selected_file3 = tk.StringVar()
    
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

    upload2_btn = tk.Button(root, text="Select Second Excel File (Optional, download the day's sales from computer)", command=upload_file2)
    upload2_btn.pack(pady=5)

    file2_label = tk.Label(root, text="No second file selected")
    file2_label.pack()

    # Upload file #3 (optional)
    def upload_file3():
        file_path = filedialog.askopenfilename(
            title="Select Excel File",
            initialdir=str(current_dir),
            filetypes=[("Excel Files", "*.xls *.xlsx")]
        )
        if file_path:
            selected_file3.set(file_path)
            file3_label.config(text=f"File 3 Selected: {file_path}")

    upload3_btn = tk.Button(root, text="Select Third Excel File (Optional, USE WITH CAUTION)", command=upload_file3)
    upload3_btn.pack(pady=5)

    file3_label = tk.Label(root, text="No third file selected")
    file3_label.pack()

    # pdf progress bar and label
    progress_var = tk.DoubleVar()
    progress_bar = ttk.Progressbar(root, variable=progress_var, maximum=100)
    progress_bar.pack(fill='x', padx=20, pady=10)

    progress_label = tk.Label(root, text="")
    progress_label.pack()

    # Transit API progress
    transit_progress_var = tk.DoubleVar()

    transit_progress_bar = ttk.Progressbar(
        root,
        variable=transit_progress_var,
        maximum=100
    )

    transit_progress_bar.pack(fill='x', padx=20, pady=10)

    transit_progress_label = tk.Label(root, text="")
    transit_progress_label.pack()

    bypass_holds_var = tk.BooleanVar(value=True)

    bypass_holds_check = tk.Checkbutton(
        root,
        text="Bypass Holds",
        variable=bypass_holds_var
    )
    bypass_holds_check.pack(pady=10)

    # Run button
    def update_progress(value, key):
        progress_var.set(value)
        progress_label.config(text=f"Processing: {key}")
        root.update_idletasks()

    def update_transit_progress(value, key):
        progress_var.set(value)
        progress_label.config(text=f"Transit Lookup: {key}")
        root.update_idletasks()

    def on_run():
        file1 = selected_file1.get().strip()
        file2 = selected_file2.get().strip() or None
        file3 = selected_file3.get().strip() or None
        bypass_holds = bypass_holds_var.get()

        if not file1:
            messagebox.showerror("Error", "Please select the first Excel file.")
            return

        try:
            output = run_processing(
                file1,
                file2,
                file3,
                progress_callback=update_progress,
                transit_progress_callback=update_transit_progress,
                bypass_future_hold=bypass_holds
            )
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
    try:
        # run_processing("default4.xlsx", bypass_future_hold=True)  # For testing without GUI
        run_gui()
    except Exception as e:
        print(f"An error occurred: {e}")
