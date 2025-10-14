from pathlib import Path
from reportlab.lib.pagesizes import letter
from generate_pick_sheet import generate_pick_sheet
from numbered_canvas import NumberedCanvas
from order_utils import excel_to_dicts, group_data, sort_grouped_data, get_date_range
from weather import get_alerting_forecast
import os
import sys

def main():
    # Determine current directory based on execution context
    if getattr(sys, 'frozen', False):
        current_dir = Path(sys.executable).parent
    else:
        current_dir = Path('.')

    # Find Excel files (.xlsx and .xls) in current directory
    excel_files = list(current_dir.glob("*.xlsx")) + list(current_dir.glob("*.xls"))

    if len(excel_files) == 0 or len(excel_files) > 2:
        print("Error: only supports one or two files in directory.")
        return

    if len(excel_files) == 1:
        # Single file processing
        data = excel_to_dicts(excel_files[0])
        grouped_data = group_data(data)
        _, max_date = get_date_range(grouped_data)
        formatted = max_date.strftime("%A_%m-%d-%y")
        sorted_grouped_data = sort_grouped_data(grouped_data)

        filename = f"{formatted}.pdf"
        c = NumberedCanvas(filename, pagesize=letter)
        groups = []
        for key in sorted_grouped_data:
            groups.append(generate_pick_sheet(c, sorted_grouped_data[key]))
            # print(sorted_grouped_data[key]['address'])
            # print(get_alerting_forecast(sorted_grouped_data[key]['address']))
            c.showPage()
        c.set_groups(groups)
        c.save()

    else:
        # Two files processing
        data0 = excel_to_dicts(excel_files[0])
        data1 = excel_to_dicts(excel_files[1])
        grouped_data0 = group_data(data0)
        grouped_data1 = group_data(data1)
        _, max_date0 = get_date_range(grouped_data0)
        _, max_date1 = get_date_range(grouped_data1)

        # Swap to ensure chronological order by max_date
        if max_date0 > max_date1:
            data0, data1 = data1, data0
            grouped_data0, grouped_data1 = grouped_data1, grouped_data0
            max_date0, max_date1 = max_date1, max_date0

        if max_date0 > min(get_date_range(grouped_data1)):
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
        formatted = max_date1.strftime("%A_%m-%d-%y")

        filename = f"{formatted}.pdf"
        c = NumberedCanvas(filename, pagesize=letter)
        groups = []
        for key in sorted_grouped_data:
            groups.append(generate_pick_sheet(c, sorted_grouped_data[key], boxed=True))
            c.showPage()
        c.set_groups(groups)
        c.save()

    print(f"PDF created: {filename}")
    os.system(f'open "{filename}"')

if __name__ == "__main__":
    main()