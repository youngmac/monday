## Build
 `/Library/Frameworks/Python.framework/Versions/3.10/bin/pyinstaller --onefile --windowed --name=ConvertApp convert.py`

## Usage

Add one excel file to the same directory as this app and it will create pick sheets for all items.

Add two excel files to the same directory as this app and it will create pick sheets for all items in the later excel file, linking against the first file. If there are conficting dates, it will throw an error.