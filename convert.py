from pathlib import Path
from reportlab.lib.pagesizes import letter
from generate_pages import generate_pick_sheet, generate_order_summary, generate_customer_summary
from numbered_canvas import NumberedCanvas
from order_utils import excel_to_dicts, group_data, sort_grouped_data, get_date_range, aggregate_data
import os
import sys

def generate_pages(c, sorted_grouped_data, aggregated_data, plants, max_date, blocked=False, final_uid=0):
    groups = []
    single_item_orders = []
    pick_sheet_index = 1

    groups.append(generate_order_summary(c, aggregated_data, plants, max_date))

    for key in sorted_grouped_data:
        if len(sorted_grouped_data[key]["items"]) == 1 and sorted_grouped_data[key]["uid"] > final_uid:
            single_item_orders.append(sorted_grouped_data[key])
            continue

        print(f"Generating pick sheet for {key} ..." + str(pick_sheet_index))
        pick_sheet_index += 1
        groups.append(generate_pick_sheet(c, sorted_grouped_data[key], blocked))           
        c.showPage()

    groups.append(generate_customer_summary(c, single_item_orders))
    return groups

def main():
    # Determine current directory based on execution context
    if getattr(sys, 'frozen', False):
        current_dir = Path(sys.executable).parent
    else:
        current_dir = Path('.')

    # Find Excel files (.xlsx and .xls) in current directory
    excel_files = list(current_dir.glob("*.xlsx")) + list(current_dir.glob("*.xls"))

    if len(excel_files) == 0:
        print("Error: No excel file in current directory.")
        return

    if len(excel_files) == 1:
        # Single file processing
        data = excel_to_dicts(excel_files[0])
        grouped_data = group_data(data)
        _, max_date = get_date_range(grouped_data)
        formatted = max_date.strftime("%A_%m-%d-%y")
        sorted_grouped_data = sort_grouped_data(grouped_data)
        aggregated_data, plants = aggregate_data(sorted_grouped_data)

        filename = f"{formatted}.pdf"
        c = NumberedCanvas(filename, pagesize=letter)

        c.set_groups(generate_pages(c, sorted_grouped_data, aggregated_data, plants, max_date))
        c.save()

    else: # get two latest files
        datas = []
        for file in excel_files:
            grouped_data = group_data(excel_to_dicts(file))
            _, max_date = get_date_range(grouped_data)
            datas.append({"grouped_data": grouped_data, "date": max_date})

        datas.sort(key=lambda item: item["date"], reverse=True)

        # Two or more files processing (date 1 > date 0)
        grouped_data0 = datas[1]["grouped_data"]
        grouped_data1 = datas[0]["grouped_data"]
        max_date0 = datas[1]["date"]
        max_date1 = datas[0]["date"]

        if max_date0 >= min(get_date_range(grouped_data1)):
            print("Error: Date ranges of the two files overlap.")
            return

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
        aggregated_data, plants = aggregate_data(sorted_grouped_data)
        formatted = max_date1.strftime("%A_%m-%d-%y")

        filename = f"{formatted}.pdf"
        c = NumberedCanvas(filename, pagesize=letter)

        c.set_groups(generate_pages(c, sorted_grouped_data, aggregated_data, plants, max_date1, True, len(sorted_grouped_data0)))
        c.save()

    print(f"PDF created: {filename}")
    os.system(f'open "{filename}"')

if __name__ == "__main__":
    main()