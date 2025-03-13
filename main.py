import sys
import sqlite3
import csv
import datetime
import logging
import requests
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget, QComboBox, QTableWidget, QTableWidgetItem,
    QLineEdit, QPushButton, QMessageBox, QHBoxLayout, QInputDialog, QFileDialog, QTabWidget, QMenuBar, QAction,
    QStatusBar, QDialog, QVBoxLayout, QTextEdit, QStackedWidget, QToolBar, QStyle
)
from PyQt5.QtGui import QFont, QIcon, QColor, QPixmap, QPalette
from PyQt5.QtCore import Qt, QTimer, QObject, QEvent, QPropertyAnimation, QEasingCurve
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

# Konstant
DB_FILE = "rfid_users.db"
LOG_FILE = "logg.txt"
CSV_FILE = "rfid_log.csv"
BACKUP_CSV_FILE = "backup_rfid_log.csv"
CLEAR_DELAY = 3000  # 3 sekunder
LOGO_URL = "https://github.com/filip243520/CardReader/raw/main/Media-removebg-preview.png"  # Loggans URL

# Konfigurera loggning
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(message)s')

# Ladda loggan
def load_logo():
    try:
        response = requests.get(LOGO_URL)
        if response.status_code == 200:
            with open("presencepoint_logo.png", "wb") as file:
                file.write(response.content)
            return QPixmap("presencepoint_logo.png")  # Använd QPixmap direkt
        else:
            logging.error(f"Kunde inte ladda loggan: HTTP-fel {response.status_code}")
            return QPixmap()  # Tom QPixmap om det inte går att ladda
    except Exception as e:
        logging.error(f"Fel vid inläsning av logga: {e}")
        return QPixmap()  # Tom QPixmap vid fel

# Språk
LANGUAGES = {
    "sv": {
        "welcome": "Välkommen! Skanna ditt kort.",
        "scan_prompt": "Skanna ditt RFID-kort...",
        "unknown_card": "Okänt kort",
        "register_prompt": "Kortet är inte registrerat. Vill du registrera det nu?",
        "register_success": "Kortet har registrerats för {} ({})!",
        "delete_user": "Ta bort användare",
        "delete_confirm": "Är du säker på att du vill ta bort {}?",
        "clear_logs": "Rensa loggar",
        "clear_logs_confirm": "Är du säker på att du vill rensa loggarna?",
        "clear_db": "Rensa databas",
        "clear_db_confirm": "Är du säker på att du vill rensa databasen?",
    },
    "en": {
        "welcome": "Welcome! Scan your card.",
        "scan_prompt": "Scan your RFID card...",
        "unknown_card": "Unknown card",
        "register_prompt": "The card is not registered. Do you want to register it now?",
        "register_success": "The card has been registered for {} ({})!",
        "delete_user": "Delete user",
        "delete_confirm": "Are you sure you want to delete {}?",
        "clear_logs": "Clear logs",
        "clear_logs_confirm": "Are you sure you want to clear the logs?",
        "clear_db": "Clear database",
        "clear_db_confirm": "Are you sure you want to clear the database?",
    }
}

CURRENT_LANGUAGE = "sv"  # Standard språk

def tr(key):
    """Hämta översättning för en given nyckel."""
    return LANGUAGES[CURRENT_LANGUAGE].get(key, key)

def initialize_database():
    """Initiera databasen och skapa tabeller om de inte finns."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Skapa tabellen 'users' om den inte finns
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                name TEXT,
                school_class TEXT
            )
        """)
        logging.info("Tabellen 'users' skapad eller redan existerar.")
        
        # Skapa tabellen 'scans' om den inte finns
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id TEXT,
                timestamp TEXT
            )
        """)
        logging.info("Tabellen 'scans' skapad eller redan existerar.")
        
        # Lägg till fördefinierade användare om de inte redan finns
        predefined_users = [
            ("1095297406", "Sunny Gran", "23TEP"),
            ("0271340527", "Eveline Lim", "23TEI")
        ]
        for card_id, name, school_class in predefined_users:
            cursor.execute("INSERT OR IGNORE INTO users (id, name, school_class) VALUES (?, ?, ?)", (card_id, name, school_class))
            logging.info(f"Försökte lägga till användare: {card_id}, {name}, {school_class}")
        
        conn.commit()
        logging.info("Databas initierad och fördefinierade användare tillagda.")
    except sqlite3.Error as e:
        logging.error(f"Databasfel: {e}")
    finally:
        conn.close()

def initialize_csv():
    """Initiera CSV-filen om den inte finns."""
    try:
        with open(CSV_FILE, "w", newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(["Namn", "Klass", "Tidstämpel"])
        logging.info("CSV-fil initierad.")
    except IOError as e:
        logging.error(f"Filfel: {e}")

def register_card(card_id, name, school_class):
    """Registrera ett nytt kort i databasen."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (id, name, school_class) VALUES (?, ?, ?)", (card_id, name, school_class))
        conn.commit()
        logging.info(f"Kort registrerat: {card_id}, {name}, {school_class}")
        export_to_csv(BACKUP_CSV_FILE)  # Skapa en backup av databasen
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
        logging.info(f"Databasfråga för kort-ID '{card_id}': Resultat = {result}")
        return result if result else (None, None)
    except sqlite3.Error as e:
        logging.error(f"Databasfel: {e}")
        return None, None
    finally:
        conn.close()

def log_scan(card_id):
    """Logga skanningen i databasen och CSV-filen."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        # Logga skanningen i databasen
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO scans (card_id, timestamp) VALUES (?, ?)", (card_id, timestamp))
        conn.commit()
        logging.info(f"Skanning loggad i databas: {card_id}, {timestamp}")
    except sqlite3.Error as e:
        logging.error(f"Databasfel: {e}")
    finally:
        conn.close()

    # Logga skanningen i CSV-filen (utan kort-ID)
    try:
        name, school_class = get_user_info(card_id)
        with open(CSV_FILE, "a", newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow([name if name else "Okänd", school_class if school_class else "Okänd", timestamp])
        logging.info(f"Skanning loggad i CSV-fil: {name}, {school_class}, {timestamp}")
    except IOError as e:
        logging.error(f"Filfel: {e}")

def clear_csv_file():
    """Rensa innehållet i CSV-filen."""
    try:
        with open(CSV_FILE, "w", newline='', encoding='utf-8') as file:
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
        export_to_csv(BACKUP_CSV_FILE)  # Skapa en backup av databasen
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

def export_to_csv(file_path=None):
    """Exportera användarlistan och skanningar till en CSV-fil."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()
        cursor.execute("SELECT * FROM scans")
        scans = cursor.fetchall()

        if not file_path:
            file_path, _ = QFileDialog.getSaveFileName(None, "Spara data", "", "CSV-filer (*.csv)")

        if file_path:
            with open(file_path, "w", newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(["PresencePoint - RFID Logg"])
                writer.writerow(["Namn", "Klass", "Tidstämpel"])
                for user in users:
                    writer.writerow([user[1], user[2], ""])
                for scan in scans:
                    writer.writerow(["", "", scan[2]])
            logging.info(f"Data exporterad till {file_path}")
    except sqlite3.Error as e:
        logging.error(f"Databasfel: {e}")
    except IOError as e:
        logging.error(f"Filfel: {e}")
    finally:
        conn.close()

def import_users_from_csv():
    """Importera användare från en CSV-fil."""
    file_path, _ = QFileDialog.getOpenFileName(None, "Öppna CSV-fil", "", "CSV-filer (*.csv)")
    if file_path:
        try:
            with open(file_path, "r", encoding='utf-8') as file:
                reader = csv.reader(file)
                next(reader)  # Hoppa över rubrikraden
                rows = list(reader)

                # Visa en förhandsgranskning av datan
                preview_dialog = QDialog()
                preview_dialog.setWindowTitle("Förhandsgranska CSV-fil")
                preview_layout = QVBoxLayout()
                preview_text = QTextEdit()
                preview_text.setReadOnly(True)
                preview_text.setText("\n".join([", ".join(row) for row in rows]))
                preview_layout.addWidget(preview_text)
                confirm_button = QPushButton("Importera")
                confirm_button.clicked.connect(preview_dialog.accept)
                preview_layout.addWidget(confirm_button)
                preview_dialog.setLayout(preview_layout)

                if preview_dialog.exec_() == QDialog.Accepted:
                    for row in rows:
                        if len(row) >= 3:
                            card_id, name, school_class = row[0], row[1], row[2]
                            register_card(card_id, name, school_class)
                    logging.info(f"Användare importerade från {file_path}")
        except IOError as e:
            logging.error(f"Filfel: {e}")

class RFIDScannerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PresencePoint - RFID Scanner App")
        self.setGeometry(300, 200, 800, 600)
        self.setStyleSheet("background-color: #2E2E2E; color: white;")
        
        # Ladda loggan
        self.logo_pixmap = load_logo()
        self.setWindowIcon(QIcon(self.logo_pixmap))  # Använd QPixmap för att skapa en QIcon

        # Menyrad
        self.menu_bar = self.menuBar()
        self.file_menu = self.menu_bar.addMenu("Arkiv")
        
        # Exportera data
        export_action = QAction("Exportera data", self)
        export_action.triggered.connect(export_to_csv)
        self.file_menu.addAction(export_action)
        
        # Rensa loggar
        clear_logs_action = QAction("Rensa loggar", self)
        clear_logs_action.triggered.connect(self.clear_logs)
        self.file_menu.addAction(clear_logs_action)
        
        # Rensa databas
        clear_db_action = QAction("Rensa databas", self)
        clear_db_action.triggered.connect(self.clear_database_prompt)
        self.file_menu.addAction(clear_db_action)

        # Statusfält
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(tr("welcome"))

        # Lägg till logga i statusfältet
        logo_label = QLabel()
        logo_label.setPixmap(self.logo_pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))  # Skala loggan till 32x32
        self.status_bar.addPermanentWidget(logo_label)

        # Lägg till lite marginaler runt loggan
        self.status_bar.setStyleSheet("QStatusBar::item { border: none; margin: 2px; }")

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout()
        self.central_widget.setLayout(self.layout)

        # Meny
        self.menu = QComboBox()
        self.menu.addItems(["Skanna kort", "Visa användare", "Visa senaste skanningar", "Statistik", "Registrera kort", "Rensa loggar", "Exportera data", "Importera användare", "Rensa databas"])
        self.menu.currentIndexChanged.connect(self.switch_page)
        self.menu.setStyleSheet("""
            QComboBox {
                background-color: #444;
                color: white;
                font-size: 16px;
                padding: 5px;
                border-radius: 5px;
                border: 1px solid #555;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: url(arrow.png);
                width: 14px;
                height: 14px;
            }
        """)
        self.layout.addWidget(self.menu)

        # Utgångsetikett
        self.output_label = QLabel(tr("welcome"))
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
        self.output_label.setText(tr("scan_prompt"))
        self.current_frame = QWidget()
        self.layout.addWidget(self.current_frame)

    def show_user_list(self):
        """Visa alla registrerade användare."""
        self.clear_page()
        self.output_label.setText("Registrerade användare")

        self.current_frame = QWidget()
        table_layout = QVBoxLayout(self.current_frame)

        # Lägg till sökruta
        search_box = QLineEdit()
        search_box.setPlaceholderText("Sök efter namn eller klass...")
        search_box.textChanged.connect(self.filter_user_table)
        table_layout.addWidget(search_box)

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

    def filter_user_table(self, text):
        """Filtrera användarlistan baserat på söktext."""
        for row in range(self.user_table.rowCount()):
            match = False
            for col in range(self.user_table.columnCount()):
                item = self.user_table.item(row, col)
                if item and text.lower() in item.text().lower():
                    match = True
                    break
            self.user_table.setRowHidden(row, not match)

    def show_recent_scans(self):
        """Visa de senaste skanningarna."""
        self.clear_page()
        self.output_label.setText("Senaste skanningar")

        self.current_frame = QWidget()
        table_layout = QVBoxLayout(self.current_frame)

        # Lägg till sökruta
        search_box = QLineEdit()
        search_box.setPlaceholderText("Sök efter namn eller tidstämpel...")
        search_box.textChanged.connect(self.filter_scan_table)
        table_layout.addWidget(search_box)

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

    def filter_scan_table(self, text):
        """Filtrera skanningstabellen baserat på söktext."""
        for row in range(self.scan_table.rowCount()):
            match = False
            for col in range(self.scan_table.columnCount()):
                item = self.scan_table.item(row, col)
                if item and text.lower() in item.text().lower():
                    match = True
                    break
            self.scan_table.setRowHidden(row, not match)

    def show_statistics(self):
        """Visa statistik över antal skanningar per användare."""
        self.clear_page()
        self.output_label.setText("Statistik")

        self.current_frame = QWidget()
        table_layout = QVBoxLayout(self.current_frame)

        # Skapa ett diagram med matplotlib
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT users.name, COUNT(scans.id) 
                FROM users 
                LEFT JOIN scans ON users.id = scans.card_id 
                GROUP BY users.id 
                ORDER BY COUNT(scans.id) DESC
            """)
            stats = cursor.fetchall()
            names = [stat[0] for stat in stats]
            counts = [stat[1] for stat in stats]

            fig, ax = plt.subplots()
            ax.bar(names, counts)
            ax.set_xlabel("Användare")
            ax.set_ylabel("Antal skanningar")
            ax.set_title("Statistik över skanningar")

            # Lägg till logga som vattenstämpel
            fig.text(0.5, 0.5, "PresencePoint", fontsize=40, color='gray', alpha=0.2,
                     ha='center', va='center', rotation=30)

            canvas = FigureCanvas(fig)
            table_layout.addWidget(canvas)
        except sqlite3.Error as e:
            logging.error(f"Databasfel: {e}")
        finally:
            conn.close()

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

        # Fyll i kort-ID automatiskt om det finns ett väntande kort-ID
        if self.pending_card_id:
            self.card_id_input.setText(self.pending_card_id)
            self.card_id_input.setReadOnly(True)  # Gör fältet skrivskyddat för att undvika ändringar

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
            self.output_label.setText(tr("register_success").format(name, school_class))
            self.timer.start(CLEAR_DELAY)
            
            # Uppdatera gränssnittet och gå tillbaka till skanningssidan
            self.show_scan_page()
            
            # Automatisk skanning efter registrering
            self.process_card_input(card_id)
            
            # Rensa pending_card_id
            self.pending_card_id = None
        else:
            self.output_label.setText("Fyll i alla fält!")

    def delete_user_from_table(self, row):
        """Ta bort en användare från tabellen och databasen."""
        card_id = self.user_table.item(row, 0).text()
        reply = QMessageBox.question(self, tr("delete_user"), tr("delete_confirm").format(card_id),
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            delete_user(card_id)
            self.show_user_list()  # Uppdatera användarlistan

    def process_card_input(self, card_id):
        """Hantera kortskanning."""
        card_id = card_id.strip()
        logging.info(f"Bearbetar kortinmatning: '{card_id}'")

        if not card_id:
            logging.warning("Tomt kort-ID mottaget.")
            return

        name, school_class = get_user_info(card_id)
        logging.info(f"Användarinformation: Namn = {name}, Klass = {school_class}")

        if name:
            log_scan(card_id)  # Logga skanningen i både databasen och CSV-filen
            self.output_label.setText(f"{name} ({school_class}) har skannat in sig")
            self.timer.start(CLEAR_DELAY)
        else:
            # Fråga användaren om de vill registrera kortet
            reply = QMessageBox.question(
                self,
                tr("unknown_card"),
                tr("register_prompt"),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            if reply == QMessageBox.Yes:
                self.output_label.setText("Registrera nytt kort")
                self.show_register_form()
                self.pending_card_id = card_id  # Spara kort-ID för att fylla i formuläret automatiskt
            else:
                self.output_label.setText(tr("scan_prompt"))

    def clear_output(self):
        """Rensa meddelandet efter en fördröjning."""
        self.output_label.setText(tr("scan_prompt"))
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
            self.clear_logs()
        elif index == 6:
            export_to_csv()
        elif index == 7:
            import_users_from_csv()
        elif index == 8:
            self.clear_database_prompt()

    def clear_logs(self):
        """Rensa loggarna."""
        reply = QMessageBox.question(self, tr("clear_logs"), tr("clear_logs_confirm"),
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            clear_csv_file()
            self.output_label.setText("Loggar rensade!")
            self.timer.start(CLEAR_DELAY)

    def clear_database_prompt(self):
        """Fråga användaren om de vill rensa databasen."""
        reply = QMessageBox.question(self, tr("clear_db"), tr("clear_db_confirm"),
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
                if self.buffer:  # Kontrollera att bufferten inte är tom
                    self.app_window.process_card_input(self.buffer)
                self.buffer = ""  # Återställ buffern efter bearbetning
                logging.info(f"Buffert återställd efter bearbetning av kort: {self.buffer}")
        return super().eventFilter(obj, event)

def main():
    initialize_database()
    initialize_csv()
    app = QApplication(sys.argv)
    window = RFIDScannerApp()
    key_filter = KeyEventFilter(window)
    app.installEventFilter(key_filter)
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
