import sqlite3
import unittest
from inference import Processor
from unittest.mock import patch, MagicMock
from datetime import datetime

class TestProcessor(unittest.TestCase):

    @patch('pickle.load')
    @patch('builtins.open')
    def setUp(self, mock_open, mock_pickle_load):
        # Mock the model loading process
        self.processor = Processor(model_path='../model/model.pkl')


    def test_process_pas_admission(self):
        # Test processing of a PAS admission message
        dob = datetime.now()
        self.processor.process_pas(is_admission=True, mrn=1, sex='M',dob=dob)
        with sqlite3.connect(self.processor.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT sex, DOB from Patients WHERE MRN = 1
            """)
            selected = cursor.fetchone() 
        self.assertEqual(selected[0], 'M')
        self.assertEqual(selected[1],str(dob))

    def test_process_lims(self):
        # Test processing of a LIMS message for someone with existing data
        mrn = 822825
        results = [68.58, 70.58, 64.15, 48.39, 58.01, 85.93]
        dates = ['2024-01-01 06:12:00', '2024-01-09 10:48:00', '2024-01-09 14:20:00', '2024-01-10 17:29:00', '2024-01-17 06:27:00', '2024-01-23 17:55:00']
        with sqlite3.connect(self.processor.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE from BloodTests WHERE MRN = 822825")
            for i in range(len(results)):
                
                cursor.execute("INSERT INTO BloodTests (MRN, TestDate, TestResult) VALUES (?, ?, ?)", (mrn, dates[i], results[i]))
        prediction = self.processor.process_lims(mrn=mrn, test_date=datetime.now(), test_result=99.0)
        with sqlite3.connect(self.processor.db_path) as conn:
            cursor.execute("SELECT * from BloodTests WHERE MRN = 822825")
            query_result = cursor.fetchall()
        self.assertIsNotNone(prediction)
        print(query_result)
        self.assertEqual(len(query_result), 7)

    def test_make_prediction_missing_data(self):
        # Test make_prediction with missing data
        self.processor.patient_data[2] = {'tests': [], 'dates': [], 'min': None, 'mean': None, 'test_count': 0}
        prediction = self.processor.make_prediction(mrn=2,latest_test_date=datetime.now(), latest_result=11)
        self.assertIsNone(prediction)

if __name__ == '__main__':
    unittest.main()
