# main.py

import sys
import traceback
from PyQt5.QtWidgets import QApplication
from ui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()



def exception_hook(exc_type, exc_value, exc_traceback):
    print("Uncaught exception:", exc_type, exc_value)
    traceback.print_exception(exc_type, exc_value, exc_traceback)
    sys.exit(1)

sys.excepthook = exception_hook