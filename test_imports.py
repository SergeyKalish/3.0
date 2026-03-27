#!/usr/bin/env python3
import sys
print("Python:", sys.executable)
print("=" * 50)

try:
    print("1. Importing PyQt5...")
    from PyQt5.QtWidgets import QApplication, QWidget
    print("   PyQt5 OK")
    
    print("2. Importing img2pdf...")
    import img2pdf
    print("   img2pdf OK")
    
    print("3. Creating QApplication...")
    app = QApplication(sys.argv)
    print("   QApplication OK")
    
    print("4. Creating QWidget...")
    w = QWidget()
    w.setWindowTitle("Test")
    w.resize(200, 100)
    w.show()
    print("   QWidget shown")
    
    print("5. Starting event loop...")
    print("   (Close window to exit)")
    sys.exit(app.exec_())
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    input("Press Enter to exit...")
