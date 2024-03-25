import unittest
import os
import sqlite3
from datetime import datetime
from database import Database

class DatabaseTest(unittest.TestCase):
    def setUp(self):
        # Create a temporary database for testing
        self.db_path = "../state/test_patient_data.db"
        self.history_path = "../tests/test_history.csv"
        self.database = Database(self.db_path, self.history_path)

    def tearDown(self):
        # Remove the temporary database after testing
        os.remove(self.db_path)

    def test_initialize_database(self):
        # Check if the Patients and BloodTests tables are created
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Patients'")
            self.assertIsNotNone(cursor.fetchone())
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='BloodTests'")
            self.assertIsNotNone(cursor.fetchone())

    def test_preprocess_history(self):
        # Check if the history file is correctly processed and inserted into the database
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Check if the patient and blood test data are inserted correctly
            cursor.execute("SELECT COUNT(*) FROM Patients")
            self.assertEqual(cursor.fetchone()[0], 2)  # Assuming there are 2 patients in the test history file

            cursor.execute("SELECT COUNT(*) FROM BloodTests")
            self.assertEqual(cursor.fetchone()[0], 8)  # Assuming there are 4 blood tests in the test history file

            # Check if the TestSummary table is updated correctly
            cursor.execute("SELECT MinTestResult, MeanTestResult, TestCount FROM Patients WHERE MRN = 822825")
            result = cursor.fetchone()
            self.assertEqual(result[0], 48.39)  
            self.assertEqual(result[1], 65.94)  
            self.assertEqual(result[2], 6)  


if __name__ == "__main__":
    unittest.main()