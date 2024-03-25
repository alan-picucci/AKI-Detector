#!/usr/bin/env python3
import requests
from datetime import datetime
import socket
import hl7
from inference import Processor
import threading
import pandas as pd
import argparse
import os
import time
from prometheus_client import Counter, start_http_server, Summary, Gauge, Histogram
import signal

MLLP_BUFFER_SIZE = 1024
MLLP_START_OF_BLOCK = b'\x0b'
MLLP_END_OF_BLOCK = b'\x1c'
MLLP_CARRIAGE_RETURN = b'\x0d'

class Client():
    def __init__(self, mllp_port = 8440, pager_port = 8441, mllp_host = "localhost", pager_host = "localhost", history_path = "../data/history.csv", db_path = "../state/patient_data.db", metrics = False):
        """Init function for the client

        Args:
            mllp_port (int, optional): Port for MLLP messages. Defaults to 8440.
            pager_port (int, optional): Port for pages. Defaults to 8441.
            mllp_host (str, optional): MLLP host's address. Defaults to "localhost".
            pager_host (str, optional): Page host's address. Defaults to "localhost".
            history_path (str, optional): History file path. Defaults to "./data/history.csv".
            db_path (str, optional): Database path. Defaults to "./state/patient_data.db".
        """
        self.mllp_port = mllp_port
        self.pager_port = pager_port
        self.mllp_host = mllp_host
        self.pager_host = pager_host
        self.metrics = metrics
        if metrics:
            latency_buckets = [0.005, 0.01, 0.015, 0.02, 0.025, 0.03, 0.035, 0.04, 0.045, 0.05, 0.1, 0.25, 0.5, 0.75, 1, 2, 3]
            self.request_latency = Histogram('request_latency_seconds', 'Time spent processing request', buckets = latency_buckets)
            self.messages = Counter('hl7_messages', 'Number of HL7 messages received')
            self.page_requests = Counter('page_requests', 'Number of page requests issued')
            self.admissions = Counter('admissions', 'Number of admissions')
            self.discharges = Counter('discharges', 'Number of discharges')
            self.lab_results = Counter('lab_results', 'Number of lab results')
            self.patients_in_hospital = Gauge('patients_in_hospital', 'Number of patients in the hospital')
            test_results_buckets = [50, 75, 100, 125, 150, 173, 200, 225, 250, 275, 300]
            self.test_results = Histogram('test_results', 'Test results', buckets = test_results_buckets)
            self.page_response_not_200 = Counter('page_response_not_200', 'Number of page requests with non-200 response')
            self.page_failed = Counter('page_failed', 'Number of page requests that failed')
            self.connection_closed = Counter('connection_closed', 'Number of connections closed')
        self.processor = Processor(history_path = history_path, db_path = db_path)
        print("processor initialized")
        self.predicted = []

    def send_acknowledgement(self, client_socket, status = "AA"):
        """Sends the acknowledgement of the message received

        Args:
            client_socket (socket): Socket connected to the simulator
            status (str, optional): Type of acknowledgement to send. Defaults to "AA".
        """
        ack_message = f"MSH|^~\\&|||||{datetime.now().strftime('%Y%m%d%H%M%S')}||ACK|||2.5\rMSA|{status}"
        client_socket.sendall(MLLP_START_OF_BLOCK + ack_message.encode() + MLLP_END_OF_BLOCK + MLLP_CARRIAGE_RETURN)

    def receive_mllp_message(self, client_socket):
        """Receives the MLLP message sent by the simulator

        Args:
            client_socket (socket): Socket connected to the simulator

        Returns:
            Byte: Message without START and END blocks
        """
        buffer = b""
        while True:
            part = client_socket.recv(MLLP_BUFFER_SIZE)
            if not part:
                print("Connection closed by the server")
                self.connection_closed.inc()
                break
            buffer += part
            if buffer.endswith(MLLP_END_OF_BLOCK + MLLP_CARRIAGE_RETURN):
                break
            else:
                print(f"Error in MLLP server: {str(buffer)}, acknowledging error.")
                self.send_acknowledgement(client_socket, "AR")
                buffer = b""
        return buffer.strip(MLLP_START_OF_BLOCK + MLLP_END_OF_BLOCK + MLLP_CARRIAGE_RETURN)        
    
    def page_clinical_response_team(self, mrn, datetime = None):
        """Pages the clinical response team when AKI is detected

        Args:
            mrn (int): MRN of the paged patient
            datetime (Datetime, optional): Datetime of the received message. Defaults to None.
        """
        # Targeting the local pager system on port 8441
        #url = "http://localhost:8441/page"
        url = f"http://{self.pager_host}:{self.pager_port}/page"
        headers = {'Content-type': 'text/plain'}
        if datetime:
            message = str(mrn) + "," + str(datetime)
        else:
            message = str(mrn)

        page_try_counter = 0
        
        while True:
            # Make the HTTP POST request with the MRN as the body
            response = requests.post(url, data=message, headers=headers)
            if response.status_code < 300:
                print(f"Page issued successfully for patient with MRN {mrn} at {datetime}.")
                break
            else:
                if page_try_counter < 30:
                    self.page_response_not_200.inc()
                    page_try_counter += 1
                    print(f"Failed to issue page. Status code: {response.status_code}, retrying in 2 seconds.")
                    time.sleep(2)
                else:
                    self.page_failed.inc()
                    print(f"Failed to issue page for 1 minute. Status code: {response.status_code}, exiting.")
                    break

    def parse_hl7_message(self, message):
        """Parses the received hl7 messages so they can be processed

        Args:
            message (Bytes): Decoded message

        Returns:
            String[]: Array with the data on the message
        """
        parsed_message = hl7.parse(message)
        message_type = str(parsed_message.segment('MSH')[9])
        
        # Dictionary to store the extracted data
        data = {
            'message_type': message_type,
            'message_datetime': datetime.strptime(str(parsed_message.segment('MSH')[7]), "%Y%m%d%H%M%S"),
            'patient_mrn': int(str(parsed_message.segment('PID')[3])),
        }
        if self.metrics:
            self.messages.inc()
        
        if message_type.startswith('ADT'):
            # Handling PAS messages (Admissions and Discharges)
            if message_type.endswith('A01'):
                # Patient admission only
                data['patient_dob'] = datetime.strptime(str(parsed_message.segment('PID')[7]), "%Y%m%d")
                data['patient_sex'] = str(parsed_message.segment('PID')[8])
                data['patient_name'] = str(parsed_message.segment('PID')[5])
                if self.metrics:
                    self.admissions.inc()
                    self.patients_in_hospital.inc()
                
            else:
                if self.metrics:
                    self.discharges.inc()
                    self.patients_in_hospital.dec()
        
            
        elif message_type.startswith('ORU'):
            # Handling LIMS messages (Lab Results)
            data['raw_datetime'] = str(parsed_message.segment('OBR')[7])
            data['test_datetime'] = datetime.strptime(str(parsed_message.segment('OBR')[7]), "%Y%m%d%H%M%S")
            data['test_type'] = str(parsed_message.segment('OBX')[3])
            data['test_result'] = max(0, min(500, float(str(parsed_message.segment('OBX')[5]))))
            if self.metrics:
                self.lab_results.inc()
        
        
        return data
    
    def calculate_age(self, msg_date, dob):
        """Calculates the age of the patient

        Args:
            msg_date (Datetime): Date of the message received
            dob (Datetime): Date of birth of the patient

        Returns:
            int : Age, in years, of the patient to the day of the message 
        """
        age = (msg_date-dob).days//365.2425
        return age

    def main(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            counter = 0
            # Retry connection to MLLP server for 1 minute
            while True:
                try:
                    sock.connect((self.mllp_host, self.mllp_port))
                    print(f"Connected to MLLP server on port {self.mllp_port}")
                    break
                except Exception as e:
                    if counter < 30:
                        counter += 1
                        print(f"Non fatal error: {e}, retrying in 2 seconds.")
                        time.sleep(2)
                    else:
                        print(f"Couldn't establish connection after 1 minute, exiting.")
                        sock.close()
                        return 

            try:
                while True:
                    message = self.receive_mllp_message(sock)
                    if message:
                        with self.request_latency.time():
                            decoded_message = message.decode("utf-8")
                            #print("Received message:", decoded_message)
                            parsed_message = self.parse_hl7_message(decoded_message)
                        
                            if parsed_message['message_type'].startswith('ADT'):
                                if parsed_message['message_type'].endswith('A01'):
                                    #age = self.calculate_age(parsed_message['message_datetime'], parsed_message['patient_dob'])
                                    self.processor.process_pas(True, parsed_message['patient_mrn'], parsed_message['patient_sex'], parsed_message['patient_dob'])
                                else:
                                    self.processor.process_pas(False, parsed_message['patient_mrn'], None, None)
                                    
                            elif parsed_message['message_type'].startswith('ORU'):
                                self.test_results.observe(parsed_message['test_result'])
                                pred = self.processor.process_lims(parsed_message['patient_mrn'], parsed_message['test_datetime'], parsed_message['test_result'])
                                if pred == 1:
                                    # start a new thread to page the clinical response team
                                    self.page_requests.inc()
                                    self.predicted += [parsed_message['patient_mrn']]
                                    t = threading.Thread(target=self.page_clinical_response_team, args=(str(parsed_message['patient_mrn']), str(parsed_message['raw_datetime'])))
                                    #self.page_clinical_response_team(str(parsed_message['patient_mrn']))  
                                    t.start()
                                
                    else:
                        break
                    self.send_acknowledgement(sock) # send acknoledgement after processing the message
            except KeyboardInterrupt:
                print("Client shutting down.")
            except Exception as e:
                print(f"Error: {e}")

def sigterm_handler(sig, frame):
    """Handles when SIGTERM is received

    Args:
        sig (Signal): Signal received
        frame (): Excecution frame
    """
    print("SIGTERM received, exiting.")
    exit(0)

if __name__ == "__main__":
    start_http_server(8000)
    start_time = datetime.now()
    if not os.path.isfile("./state/metrics.txt"):
        with open("./state/metrics.txt", "w") as f:
            
            f.write(f"Execution started at {start_time}\n")
    else:
        with open("./state/metrics.txt", "a") as f:
            f.write(f"Execution started at {start_time}\n")
    failures = Counter('failures', 'Number of failures')
    with failures.count_exceptions():
        try:
            parser = argparse.ArgumentParser()
            parser.add_argument("--history", default="./data/history.csv", help="Path to the hospital's history file")
            parser.add_argument("--persistent_path", default="./state/patient_data.db", help="Path to the persistent state file")
            flags = parser.parse_args()
            mllp_address = os.getenv('MLLP_ADDRESS', 'localhost:8440')
            pager_address = os.getenv('PAGER_ADDRESS', 'localhost:8441')
            mllp_host, mllp_port = mllp_address.split(':')
            mllp_port = int(mllp_port)
            pager_host, pager_port = pager_address.split(':')
            pager_port = int(pager_port)
            client = Client(mllp_port, pager_port, mllp_host, pager_host, history_path = flags.history, db_path = flags.persistent_path, metrics=True)
            signal.signal(signal.SIGTERM, sigterm_handler)
            client.main()
        except Exception as e:
            with open("./state/metrics.txt", "a") as f:
                f.write(f"Error: {e}\n")
                f.write(f"Exception at {datetime.now()}, total runtime: {datetime.now()-start_time}\n")
                f.write(f"Latency: {client.request_latency.observe()}\n")
                f.write(f"Messages: {client.messages}\n")
                f.write(f"Page requests: {client.page_requests}\n")
                f.write(f"Admissions: {client.admissions}\n")
                f.write(f"Discharges: {client.discharges}\n")
                f.write(f"Lab results: {client.lab_results}\n")
                f.write(f"Patients in hospital: {client.patients_in_hospital}\n")
                f.write(f"Test results: {client.test_results}\n")
                f.write(f"Page response not 200: {client.page_response_not_200}\n")
                f.write(f"Page failed: {client.page_failed}\n")
                f.write(f"Connection closed: {client.connection_closed}\n")
                f.write(f"Last MRN predicted: {client.predicted[-1]}\n")
            print(f"Error: {e}")
            raise
    
    end_time = datetime.now()
    with open("./state/metrics.txt", "a") as f:
        f.write(f"Execution ended at {end_time}, total runtime: {end_time-start_time}\n")
        
        f.write(f"Messages: {client.messages._value.get()}\n")
        f.write(f"Page requests: {client.page_requests._value.get()}\n")
        f.write(f"Admissions: {client.admissions._value.get()}\n")
        f.write(f"Discharges: {client.discharges._value.get()}\n")
        
        f.write(f"Patients in hospital: {client.patients_in_hospital._value.get()}\n")
        f.write(f"Page response not 200: {client.page_response_not_200._value.get()}\n")
        f.write(f"Page failed: {client.page_failed._value.get()}\n")
        f.write(f"Connection closed: {client.connection_closed._value.get()}\n")
        f.write(f"Last MRN predicted: {client.predicted[-1]}\n")
