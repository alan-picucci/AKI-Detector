import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime
import socket
from communication import Client

class TestClient(unittest.TestCase):

    @patch('socket.socket')
    def test_send_acknowledgement(self, mock_socket):
        # Setup
        client = Client()
        mock_client_socket = MagicMock()

        # Action
        client.send_acknowledgement(mock_client_socket)

        # Assert
        mock_client_socket.sendall.assert_called_once()
        args, _ = mock_client_socket.sendall.call_args
        self.assertTrue(args[0].startswith(b'\x0bMSH|^~\\&|||||'))  # Checks if the message starts with the correct block

    @patch('socket.socket')
    def test_receive_mllp_message(self, mock_socket):
        # Mock socket to simulate receiving a message
        mock_socket_instance = mock_socket.return_value
        mock_socket_instance.recv.side_effect = [
            b'\x0bSome HL7 message\x1c\x0d',  # Message part
            b''  # Simulate closing connection
        ]

        # Setup
        client = Client()

        # Action
        message = client.receive_mllp_message(mock_socket_instance)

        # Assert
        self.assertEqual(message, b'Some HL7 message')

    @patch('requests.post')
    def test_page_clinical_response_team(self, mock_post):
        # Setup
        client = Client()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Action
        client.page_clinical_response_team("123456")

        # Assert
        mock_post.assert_called_once_with("http://localhost:8441/page", data="123456", headers={'Content-type': 'text/plain'})
        self.assertEqual(mock_response.status_code, 200)

    def test_parse_hl7_message_admission(self):
        client = Client()
        hl7_message = "MSH|^~\\&|SIMULATION|SOUTH RIVERSIDE|||202401201630||ADT^A01|||2.5\rPID|1||478237423||DOE^JOHN||19840203|M"
        expected = {
            'message_type': 'ADT^A01',
            'message_datetime': datetime.strptime("202401201630", "%Y%m%d%H%M%S"),
            'patient_mrn': 478237423,
            'patient_dob': datetime.strptime("19840203", "%Y%m%d"),
            'patient_sex': 'M',
            'patient_name': 'DOE^JOHN'
        }
        result = client.parse_hl7_message(hl7_message)
        # Adjusting the assertion for datetime objects comparison
        self.assertEqual(result['message_type'], expected['message_type'])
        self.assertEqual(result['patient_mrn'], expected['patient_mrn'])
        self.assertEqual(result['patient_name'], expected['patient_name'])
        self.assertEqual(result['patient_sex'], expected['patient_sex'])
        self.assertEqual(result['patient_dob'].date(), expected['patient_dob'].date())
        self.assertEqual(result['message_datetime'].replace(second=0, microsecond=0), expected['message_datetime'])


if __name__ == '__main__':
    unittest.main()
