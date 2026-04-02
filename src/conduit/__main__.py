import sys
from PySide6.QtWidgets import QApplication
from conduit.ui.theme_loader import ThemeLoader
from conduit.ui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(ThemeLoader("Dark").load_stylesheet())

    window = MainWindow()
    window.show()


    sys.exit(app.exec())



if __name__ == "__main__":
    main()
