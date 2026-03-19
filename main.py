import sys
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow

def main() -> int:
    app = QApplication(sys.argv)
    
    # Ces deux chaînes servent de "namespace" pour QSettings plus tard
    app.setOrganizationName("GEORGIN")
    app.setApplicationName("Innovation")
    
    window = MainWindow()
    window.show()
    
    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())