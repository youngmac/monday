from reportlab.pdfgen import canvas
from reportlab.lib.units import inch


class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pages = []
        self.groups = []

    def showPage(self):
        # Save the drawing commands/state for the current page
        self.pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        """Add page numbering info to each saved page and then save the PDF."""
        page_count = len(self.pages)
        for page in self.pages:
            # Save current groups before updating state
            temp_groups = self.groups
            
            # Restore page state
            self.__dict__.update(page)
            
            # Restore groups after state update
            self.groups = temp_groups
            
            # Draw the page number
            self.draw_page_number(page_count)
            
            # Finalize the current page
            super().showPage()
        
        # Save the PDF file
        super().save()

    def set_groups(self, groups):
        """Set groups to organize page numbering (optional)."""
        self.groups = groups

    def draw_page_number(self, page_count):
        self.setFont("Helvetica", 16)
        if not self.groups or sum(self.groups) != page_count:
            # Simple page numbering: Page X of Y
            self.drawRightString(
                7.75 * inch,
                0.75 * inch,
                f"Page {self._pageNumber} of {page_count}"
            )
        else:
            # Grouped page numbering
            page_num = self._pageNumber
            group_index = 0
            
            # Determine which group the page belongs to and its relative number
            while page_num > self.groups[group_index]:
                page_num -= self.groups[group_index]
                group_index += 1
            
            self.drawRightString(
                7.75 * inch,
                0.75 * inch,
                f"Page {page_num} of {self.groups[group_index]}"
            )