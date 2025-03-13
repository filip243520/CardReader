import sys
import sqlite3
import csv
import datetime
import logging
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget, QComboBox, QTableWidget, QTableWidgetItem,
    QLineEdit, QPushButton, QMessageBox, QHBoxLayout, QInputDialog, QFileDialog, QTabWidget
)
from PyQt5.QtGui import QFont, QIcon, QColor, QPixmap
from PyQt5.QtCore import Qt, QTimer, QObject, QEvent

# Konstant
DB_FILE = "rfid_users.db"
LOG_FILE = "logg.txt"
CSV_FILE = "rfid_log.csv"
CLEAR_DELAY = 3000  # 3 sekunder

# Konfigurera loggning
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(message)s')

def initialize_database():
    """Initiera databasen och skapa tabeller om de inte finns."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                name TEXT,
                school_class TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id TEXT,
                timestamp TEXT
            )
        """)
        
        # Lägg till fördefinierade användare om de inte redan finns
        predefined_users = [
            ("1095297406", "Sunny Gran", "23TEP"),
            ("0271340527", "Eveline Lim", "23TEI")
        ]
        for card_id, name, school_class in predefined_users:
            cursor.execute("INSERT OR IGNORE INTO users (id, name, school_class) VALUES (?, ?, ?)", (card_id, name, school_class))
        
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Databasfel: {e}")
    finally:
        conn.close()

def register_card(card_id, name, school_class):
    """Registrera ett nytt kort i databasen."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (id, name, school_class) VALUES (?, ?, ?)", (card_id, name, school_class))
        conn.commit()
        logging.info(f"Kort registrerat: {card_id}, {name}, {school_class}")
    except sqlite3.Error as e:
        logging.error(f"Databasfel: {e}")
    finally:
        conn.close()

def get_user_info(card_id):
    """Hämta användarinformation från databasen."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT name, school_class FROM users WHERE id = ?", (card_id,))
        result = cursor.fetchone()
        return result if result else (None, None)
    except sqlite3.Error as e:
        logging.error(f"Databasfel: {e}")
        return None, None
    finally:
        conn.close()

def log_scan(card_id):
    """Logga skanningen i databasen."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO scans (card_id, timestamp) VALUES (?, ?)", (card_id, timestamp))
        conn.commit()
        logging.info(f"Skanning loggad: {card_id}, {timestamp}")
    except sqlite3.Error as e:
        logging.error(f"Databasfel: {e}")
    finally:
        conn.close()

def clear_csv_file():
    """Rensa innehållet i CSV-filen."""
    try:
        with open(CSV_FILE, "w", newline='') as file:
            file.truncate()
        logging.info("CSV-fil rensad.")
    except IOError as e:
        logging.error(f"Filfel: {e}")

def delete_user(card_id):
    """Ta bort en användare från databasen."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = ?", (card_id,))
        conn.commit()
        logging.info(f"Användare borttagen: {card_id}")
    except sqlite3.Error as e:
        logging.error(f"Databasfel: {e}")
    finally:
        conn.close()

def clear_database():
    """Rensa alla användare och skanningar från databasen."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users")
        cursor.execute("DELETE FROM scans")
        conn.commit()
        logging.info("Databas rensad.")
    except sqlite3.Error as e:
        logging.error(f"Databasfel: {e}")
    finally:
        conn.close()

def export_to_csv():
    """Exportera användarlistan och skanningar till en CSV-fil."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()
        cursor.execute("SELECT * FROM scans")
        scans = cursor.fetchall()

        file_path, _ = QFileDialog.getSaveFileName(None, "Spara data", "", "CSV-filer (*.csv)")
        if file_path:
            with open(file_path, "w", newline='') as file:
                writer = csv.writer(file)
                writer.writerow(["Typ", "Kort-ID", "Namn", "Klass", "Tidstämpel"])
                for user in users:
                    writer.writerow(["Användare", user[0], user[1], user[2], ""])
                for scan in scans:
                    writer.writerow(["Skanning", scan[1], "", "", scan[2]])
            logging.info(f"Data exporterad till {file_path}")
    except sqlite3.Error as e:
        logging.error(f"Databasfel: {e}")
    finally:
        conn.close()

def import_users_from_csv():
    """Importera användare från en CSV-fil."""
    file_path, _ = QFileDialog.getOpenFileName(None, "Öppna CSV-fil", "", "CSV-filer (*.csv)")
    if file_path:
        try:
            with open(file_path, "r") as file:
                reader = csv.reader(file)
                next(reader)  # Hoppa över rubrikraden
                for row in reader:
                    if len(row) >= 3:
                        card_id, name, school_class = row[0], row[1], row[2]
                        register_card(card_id, name, school_class)
            logging.info(f"Användare importerade från {file_path}")
        except IOError as e:
            logging.error(f"Filfel: {e}")

class RFIDScannerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RFID Scanner App")
        self.setGeometry(300, 200, 800, 600)
        self.setStyleSheet("background-color: #2E2E2E; color: white;")
        self.setWindowIcon(QIcon("app_icon.png"))

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout()
        self.central_widget.setLayout(self.layout)

        # Meny
        self.menu = QComboBox()
        self.menu.addItems(["Skanna kort", "Visa användare", "Visa senaste skanningar", "Statistik", "Registrera kort", "Rensa loggar", "Exportera data", "Importera användare", "Rensa databas"])
        self.menu.currentIndexChanged.connect(self.switch_page)
        self.menu.setStyleSheet("background-color: #444; color: white; font-size: 16px; padding: 5px; border-radius: 5px;")
        self.layout.addWidget(self.menu)

        # Utgångsetikett
        self.output_label = QLabel("Välkommen! Skanna ditt kort.")
        self.output_label.setFont(QFont("Arial", 18, QFont.Bold))
        self.output_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.output_label)

        # Timer för att rensa meddelanden
        self.timer = QTimer()
        self.timer.timeout.connect(self.clear_output)

        # Aktuell ram för dynamiskt innehåll
        self.current_frame = None
        self.pending_card_id = None
        self.show_scan_page()

    def clear_page(self):
        """Rensa det aktuella innehållet på skärmen."""
        if self.current_frame:
            self.layout.removeWidget(self.current_frame)
            self.current_frame.deleteLater()
            self.current_frame = None

    def show_scan_page(self):
        """Visa skanningsläget."""
        self.clear_page()
        self.output_label.setText("Skanna ditt RFID-kort...")
        self.current_frame = QWidget()
        self.layout.addWidget(self.current_frame)

    def show_user_list(self):
        """Visa alla registrerade användare."""
        self.clear_page()
        self.output_label.setText("Registrerade användare")

        self.current_frame = QWidget()
        table_layout = QVBoxLayout(self.current_frame)

        # Lägg till uppdateringsknapp
        refresh_button = QPushButton("Uppdatera lista")
        refresh_button.clicked.connect(self.show_user_list)
        refresh_button.setStyleSheet("background-color: #555; color: white; font-size: 14px; padding: 5px; border-radius: 5px;")
        table_layout.addWidget(refresh_button)

        self.user_table = QTableWidget()
        self.user_table.setColumnCount(3)
        self.user_table.setHorizontalHeaderLabels(["Kort-ID", "Namn", "Klass"])

        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users")
            users = cursor.fetchall()
            self.user_table.setRowCount(len(users))
            for row, user in enumerate(users):
                for col, data in enumerate(user):
                    self.user_table.setItem(row, col, QTableWidgetItem(data))
        except sqlite3.Error as e:
            logging.error(f"Databasfel: {e}")
        finally:
            conn.close()

        # Lägg till ta bort-knapp för varje användare
        for row in range(self.user_table.rowCount()):
            delete_button = QPushButton("Ta bort")
            delete_button.clicked.connect(lambda _, r=row: self.delete_user_from_table(r))
            delete_button.setStyleSheet("background-color: #ff4444; color: white; font-size: 12px; padding: 3px; border-radius: 3px;")
            self.user_table.setCellWidget(row, 2, delete_button)

        table_layout.addWidget(self.user_table)
        self.layout.addWidget(self.current_frame)

    def show_recent_scans(self):
        """Visa de senaste skanningarna."""
        self.clear_page()
        self.output_label.setText("Senaste skanningar")

        self.current_frame = QWidget()
        table_layout = QVBoxLayout(self.current_frame)

        self.scan_table = QTableWidget()
        self.scan_table.setColumnCount(3)
        self.scan_table.setHorizontalHeaderLabels(["Kort-ID", "Namn", "Tidstämpel"])

        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT scans.card_id, users.name, scans.timestamp 
                FROM scans 
                LEFT JOIN users ON scans.card_id = users.id 
                ORDER BY scans.timestamp DESC 
                LIMIT 50
            """)
            scans = cursor.fetchall()
            self.scan_table.setRowCount(len(scans))
            for row, scan in enumerate(scans):
                self.scan_table.setItem(row, 0, QTableWidgetItem(scan[0]))
                self.scan_table.setItem(row, 1, QTableWidgetItem(scan[1] if scan[1] else "Okänd"))
                self.scan_table.setItem(row, 2, QTableWidgetItem(scan[2]))
        except sqlite3.Error as e:
            logging.error(f"Databasfel: {e}")
        finally:
            conn.close()

        table_layout.addWidget(self.scan_table)
        self.layout.addWidget(self.current_frame)

    def show_statistics(self):
        """Visa statistik över antal skanningar per användare."""
        self.clear_page()
        self.output_label.setText("Statistik")

        self.current_frame = QWidget()
        table_layout = QVBoxLayout(self.current_frame)

        self.stat_table = QTableWidget()
        self.stat_table.setColumnCount(3)
        self.stat_table.setHorizontalHeaderLabels(["Namn", "Klass", "Antal Skanningar"])

        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT users.name, users.school_class, COUNT(scans.id) 
                FROM users 
                LEFT JOIN scans ON users.id = scans.card_id 
                GROUP BY users.id 
                ORDER BY COUNT(scans.id) DESC
            """)
            stats = cursor.fetchall()
            self.stat_table.setRowCount(len(stats))
            for row, stat in enumerate(stats):
                for col, data in enumerate(stat):
                    self.stat_table.setItem(row, col, QTableWidgetItem(str(data)))
        except sqlite3.Error as e:
            logging.error(f"Databasfel: {e}")
        finally:
            conn.close()

        table_layout.addWidget(self.stat_table)
        self.layout.addWidget(self.current_frame)

    def show_register_form(self):
        """Visa registreringsformulär för nya kort."""
        self.clear_page()
        self.output_label.setText("Registrera nytt kort")

        self.current_frame = QWidget()
        register_layout = QVBoxLayout(self.current_frame)

        self.card_id_input = QLineEdit()
        self.name_input = QLineEdit()
        self.class_input = QLineEdit()
        register_button = QPushButton("Registrera")

        self.card_id_input.setPlaceholderText("Kort-ID")
        self.name_input.setPlaceholderText("Namn")
        self.class_input.setPlaceholderText("Klass")

        register_button.clicked.connect(self.register_new_card)

        register_layout.addWidget(self.card_id_input)
        register_layout.addWidget(self.name_input)
        register_layout.addWidget(self.class_input)
        register_layout.addWidget(register_button)

        self.layout.addWidget(self.current_frame)

    def register_new_card(self):
        """Registrera ett nytt kort."""
        card_id = self.card_id_input.text().strip()
        name = self.name_input.text().strip()
        school_class = self.class_input.text().strip()

        if card_id and name and school_class:
            register_card(card_id, name, school_class)
            self.output_label.setText(f"Kortet har registrerats för {name} ({school_class})!")
            self.timer.start(CLEAR_DELAY)
            self.show_scan_page()
        else:
            self.output_label.setText("Fyll i alla fält!")

    def delete_user_from_table(self, row):
        """Ta bort en användare från tabellen och databasen."""
        card_id = self.user_table.item(row, 0).text()
        reply = QMessageBox.question(self, "Ta bort användare", f"Är du säker på att du vill ta bort {card_id}?",
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            delete_user(card_id)
            self.show_user_list()  # Uppdatera användarlistan

    def process_card_input(self, card_id):
        """Hantera kortskanning."""
        card_id = card_id.strip()
        logging.info(f"Bearbetar kortinmatning: {card_id}")  # Felsökning

        name, school_class = get_user_info(card_id)

        if name:
            log_scan(card_id)
            self.output_label.setText(f"{name} ({school_class}) har skannat in sig")
            self.timer.start(CLEAR_DELAY)
        else:
            self.output_label.setText("Okänt kort! Registrera det nedan:")
            self.show_register_form()

    def clear_output(self):
        """Rensa meddelandet efter en fördröjning."""
        self.output_label.setText("Skanna ditt RFID-kort...")
        self.timer.stop()

    def switch_page(self, index):
        """Byt sida baserat på menyval."""
        if index == 0:
            self.show_scan_page()
        elif index == 1:
            self.show_user_list()
        elif index == 2:
            self.show_recent_scans()
        elif index == 3:
            self.show_statistics()
        elif index == 4:
            self.show_register_form()
        elif index == 5:
            reply = QMessageBox.question(self, "Rensa loggar", "Är du säker på att du vill rensa loggarna?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                clear_csv_file()
                self.output_label.setText("Loggar rensade!")
                self.timer.start(CLEAR_DELAY)
        elif index == 6:
            export_to_csv()
        elif index == 7:
            import_users_from_csv()
        elif index == 8:
            reply = QMessageBox.question(self, "Rensa databas", "Är du säker på att du vill rensa databasen?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                clear_database()
                self.output_label.setText("Databas rensad!")
                self.timer.start(CLEAR_DELAY)

class KeyEventFilter(QObject):
    """Fånga tangenttryck och hantera kortskanning."""
    def __init__(self, app_window):
        super().__init__()
        self.app_window = app_window
        self.buffer = ""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            char = event.text()
            if char.isprintable():
                self.buffer += char
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self.app_window.process_card_input(self.buffer)
                self.buffer = ""  # Återställ buffern efter bearbetning
                logging.info(f"Buffert återställd efter bearbetning av kort: {self.buffer}")  # Felsökning
        return super().eventFilter(obj, event)

def main():
    initialize_database()
    app = QApplication(sys.argv)
    window = RFIDScannerApp()
    key_filter = KeyEventFilter(window)
    app.installEventFilter(key_filter)
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
