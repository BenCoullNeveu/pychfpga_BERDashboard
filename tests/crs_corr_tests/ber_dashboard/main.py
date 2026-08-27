# main.py
import sys
from PyQt6.QtWidgets import QApplication
from ui.dashboard import Dashboard

if __name__ == "__main__":
    app = QApplication(sys.argv)

    win = Dashboard()
    win.setWindowTitle("BER Testing UI")
    # win.resize(1200, 800)
    win.showMaximized()
    win.show()

    sys.exit(app.exec())