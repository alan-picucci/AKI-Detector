import sqlite3
import csv
import datetime
import os

class Database:
    def __init__(self, db_path="./state/patient_data.db", history_path="./data/history.csv"):
        """Init for the database

        Args:
            db_path (str, optional): Path to the database file. Defaults to "./state/patient_data.db".
            history_path (str, optional): Path to the history file. Defaults to "./data/history.csv".
        """
        self.db_path = db_path
        self.history_path = history_path
        database_existed = os.path.exists(db_path)
        self.initialize_database()
        if not database_existed:
            self.preprocess_history()
        
        

    def initialize_database(self):
        """Initialize the database and tables for the patient data.
        
        Args:
            None
        
        Returns:
            None
        """
        # Connect to SQLite database (or create if it doesn't exist)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Create Patients Table
            cursor.execute('''CREATE TABLE IF NOT EXISTS Patients (
                                MRN INTEGER PRIMARY KEY,
                                Sex TEXT,
                                DOB DATE,
                                Paged INTEGER DEFAULT 0,
                                MinTestResult REAL,
                                MeanTestResult REAL,
                                TestCount INTEGER
                            )''')

            # Create Blood Tests Table
            cursor.execute('''CREATE TABLE IF NOT EXISTS BloodTests (
                                TestID INTEGER PRIMARY KEY AUTOINCREMENT,
                                MRN INTEGER,
                                TestDate DATE,
                                TestResult REAL,
                                FOREIGN KEY(MRN) REFERENCES Patients(MRN)
                            )''')

            # The commit and connection close are automatically handled by the context manager


    def preprocess_history(self):
        """Preprocess csv file of historic test results and insert into the database.
        
        Args:
            None

        Returns:
            None
        """
        with sqlite3.connect(self.db_path) as conn, open(self.history_path, newline='') as csvfile:
            cursor = conn.cursor()
            reader = csv.reader(csvfile)
            next(reader, None)  # Skip the header row
            
            for row in reader:
                mrn = int(row[0])  # MRN is the first item
                sex = None 
                dob = None  
                
                # Check if the patient already exists
                cursor.execute("SELECT MRN FROM Patients WHERE MRN = ?", (mrn,))
                if cursor.fetchone() is None:
                    # Insert new patient
                    cursor.execute("INSERT INTO Patients (MRN, Sex, DOB) VALUES (?, ?, ?)", (mrn, sex, dob))
                
                for i in range(1, len(row), 2):
                    try:
                        #test_date = datetime.strptime(row[i], "%Y-%m-%d").date()
                        test_date = row[i]
                        test_result = float(row[i+1])
                        test_result = max(0, min(500, test_result)) # Clamp the result to a reasonable range
                        cursor.execute("INSERT INTO BloodTests (MRN, TestDate, TestResult) VALUES (?, ?, ?)", (mrn, test_date, test_result))
                    except (IndexError, ValueError):
                        continue
                
                # Update the TestSummary table
                cursor.execute("""
                    UPDATE Patients 
                    SET MinTestResult = (SELECT MIN(TestResult) FROM BloodTests WHERE MRN = ?),
                        MeanTestResult = (SELECT AVG(TestResult) FROM BloodTests WHERE MRN = ?),
                        TestCount = (SELECT COUNT(*) FROM BloodTests WHERE MRN = ?)
                    WHERE MRN = ?
                """, (mrn, mrn, mrn, mrn))
                
            conn.commit()