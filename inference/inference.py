import pandas as pd
import numpy as np
import csv
import pickle
import pandas.testing as pdt
from datetime import datetime
from database import Database
import sqlite3

class Processor:
    def __init__(self, model_path='../model/model.pkl', model_no_age_sex = "../model/model_noagesex.pkl", history_path='../data/history.csv', db_path='../state/patient_data.db'):
        with open(model_path, 'rb') as file:
            self.model = pickle.load(file)
        with open(model_no_age_sex, 'rb') as file:
            self.model_no_age_sex = pickle.load(file)

        self.history_path = history_path
        self.db_path = db_path
        self.patient_data = {}
        self.database = Database(db_path, history_path)
    
    def process_pas(self, is_admission, mrn, sex=None, dob=None):
        """Process a message from the PAS system.
        
        Args:
            is_admission (bool): Flag indicating whether the message is for admission.
            mrn (int): The medical record number of the patient
        
        Returns:
            None
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if is_admission:
                print(f"Admission message for patient {mrn}.")
                # Insert or update patient information
                cursor.execute("""
                    INSERT INTO Patients (MRN, Sex, DOB, MinTestResult, MeanTestResult, TestCount) 
                               VALUES (?, ?, ?, IFNULL((SELECT MinTestResult FROM Patients WHERE MRN = ?), 0),
                               IFNULL((SELECT MeanTestResult FROM Patients WHERE MRN = ?), 0), 
                               IFNULL((SELECT TestCount FROM Patients WHERE MRN = ?), 0))
                    ON CONFLICT(MRN) DO UPDATE SET Sex = excluded.Sex, DOB = excluded.DOB
                """, (mrn, sex, dob, mrn, mrn, mrn))
            else:
                print(f"Discharge message for patient {mrn}.")
            conn.commit()


    def process_lims(self, mrn, test_date, test_result):
        """Process a message from the LIMS system and make a prediction for the patient.
        
        Args:
            mrn (int): The medical record number of the patient.
            test_date (datetime): The date of the test in the datetime format.
            test_result (float): The result of the test.
        
        Returns:
            int: The prediction for the patient.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            
            # Insert the test result
            cursor.execute("INSERT INTO BloodTests (MRN, TestDate, TestResult) VALUES (?, ?, ?)", (mrn, test_date, test_result))
            
            

            # Retrieve current summary data for efficient updates
            cursor.execute("SELECT MinTestResult, MeanTestResult, TestCount, Paged FROM Patients WHERE MRN = ?", (mrn,))
            summary = cursor.fetchone()

            if summary:
                current_min, current_mean, current_count, paged = summary
                new_min = min(current_min, test_result) if current_min is not None else test_result
                new_mean = ((current_mean * current_count) + test_result) / (current_count + 1)
                new_count = current_count + 1

                # Update TestSummary with efficiently calculated new min, mean, and test count
                cursor.execute("""
                    UPDATE Patients
                    SET MinTestResult = ?, MeanTestResult = ?, TestCount = ?
                    WHERE MRN = ?
                """, (new_min, new_mean, new_count, mrn))

                if current_count == 0:
                    print(f"First test for patient {mrn}. Assuming no AKI.")
                    conn.commit()
                    return 0
                elif paged == 1:
                    print(f"Patient {mrn} has already been paged. No further action.")
                    conn.commit()
                    return 0
            else:
                # If it's the first test, initialize TestSummary for the patient
                new_min = new_mean = test_result
                new_count = 1

                cursor.execute("""
                    INSERT INTO Patients (MRN, Sex, DOB, MinTestResult, MeanTestResult, TestCount)
                    VALUES (?, NULL, NULL, ?, ?, ?)
                """, (mrn, new_min, new_mean, new_count))

                print(f"First test for patient {mrn}. Assuming no AKI.")
                conn.commit()
                return 0

            conn.commit()

            # Make a prediction with updated data
            y_pred = self.make_prediction(mrn, test_date, test_result)
            return y_pred
    
    
    def make_prediction(self, mrn, latest_test_date, latest_result):
        """Prepare patient data for prediction and use the trained model to predict.
        
        Args:
            mrn (int): The medical record number of the patient.

        Returns:
            int: The prediction for the patient.
        """


        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Retrieve patient's sex and dob, and the latest, min, and mean test results
            cursor.execute("""
                SELECT Sex, DOB, MinTestResult, MeanTestResult FROM Patients WHERE MRN = ?
            """, (mrn,))
            result = cursor.fetchone()

            if result:
                sex, dob, min_result, mean_result = result
                sex_encoded = 0 if sex == 'M' else 1 
                age = None
                #latest_test_date = datetime.strptime(latest_test_date, "%Y-%m-%d %H:%M:%S")
                if dob is not None:
                    dob = datetime.strptime(dob, "%Y-%m-%d %H:%M:%S")
                    age = (latest_test_date - dob).days / 365.25

                if sex_encoded is None or age is None:
                    print(f"Missing age or sex for MRN {mrn}.")
                    if None in [latest_result, min_result, mean_result]:
                        print(f"Missing data for MRN {mrn}. Cannot make prediction.")
                        return None
                    else:
                        features = pd.DataFrame({'latest_result': [latest_result], 'min_result': [min_result], 'mean_result': [mean_result]})
                        prediction = self.model_no_age_sex.predict(features)
                        if prediction[0] == 1:
                            cursor.execute("UPDATE Patients SET Paged = 1 WHERE MRN = ?", (mrn,))
                            conn.commit()
                        return prediction[0]
                else:
                    if None in [latest_result, min_result, mean_result]:
                        print(f"Missing data for MRN {mrn}. Cannot make prediction.")
                        return None
                    else:
                        features = pd.DataFrame({'age': [age], 'sex': [sex_encoded], 'latest_result': [latest_result], 'min_result': [min_result], 'mean_result': [mean_result]})
                        prediction = self.model.predict(features)
                        if prediction[0] == 1:
                            cursor.execute("UPDATE Patients SET Paged = 1 WHERE MRN = ?", (mrn,))
                            conn.commit()
                        return prediction[0]
            else:
                print(f"No data available for MRN {mrn} to make a prediction.")
                return None



if __name__ == "__main__":
    # Initialize the processor
    processor = Processor()

    # Simulate preprocessing history data
    print("Testing preprocess_history...")
    processor.preprocess_history('history.csv')  # Ensure this file exists and has the expected format
    print("Patient data after history preprocessing:", processor.patient_data)

    # Simulate processing PAS message
    print("\nTesting process_pas...")
    processor.process_pas(is_admission=True, mrn=448590, sex='M', age=30)
    print("Patient data after PAS processing for MRN 448590:", processor.patient_data.get(448590))

    # Simulate processing LIMS message
    print("\nTesting process_lims...")
    test_result = processor.process_lims(mrn=448590, test_date="2021-01-03", test_result=105)
    print("Prediction for MRN 448590 after LIMS processing:", test_result)

    # Test prediction
    print("\nTesting make_prediction...")
    prediction = processor.make_prediction(448590)
    print("Prediction for MRN 448590:", prediction)