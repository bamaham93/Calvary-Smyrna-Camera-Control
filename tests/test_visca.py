import unittest
from unittest.mock import MagicMock, patch

from visca import ViscaCamera


class ViscaCameraPositionTests(unittest.TestCase):
    @patch("visca.time.sleep")
    @patch("visca.socket.socket")
    def test_send_with_response_returns_udp_payload(self, mock_socket_factory, _mock_sleep):
        mock_socket = MagicMock()
        mock_socket_factory.return_value = mock_socket
        mock_socket.recvfrom.return_value = (b"\x90\x50\x00\x00\x00\x01\xff", ("10.0.0.1", 1259))

        camera = ViscaCamera("10.0.0.1")
        response = camera.send_with_response("81 09 04 47 FF")

        self.assertEqual(response, b"\x90\x50\x00\x00\x00\x01\xff")
        mock_socket.sendto.assert_called_once()
        mock_socket.settimeout.assert_called_once_with(1.0)

    @patch("visca.time.sleep")
    @patch("visca.socket.socket")
    def test_get_position_feedback_decodes_pan_tilt_zoom(self, mock_socket_factory, _mock_sleep):
        mock_socket = MagicMock()
        mock_socket_factory.return_value = mock_socket
        mock_socket.recvfrom.side_effect = [
            (bytes.fromhex("90 50 00 01 02 03 00 00 00 0A FF"), ("10.0.0.1", 1259)),
            (bytes.fromhex("90 50 00 0A 00 0B FF"), ("10.0.0.1", 1259)),
        ]

        camera = ViscaCamera("10.0.0.1")
        feedback = camera.get_position_feedback()

        self.assertEqual(feedback, {"pan": 0x0123, "tilt": 0x000A, "zoom": 0x0A0B})

    @patch("visca.time.sleep")
    @patch("visca.socket.socket")
    def test_get_pan_tilt_position_rejects_invalid_response(self, mock_socket_factory, _mock_sleep):
        mock_socket = MagicMock()
        mock_socket_factory.return_value = mock_socket
        mock_socket.recvfrom.return_value = (b"\x90\x41\x00\x00\x00\x00\xff", ("10.0.0.1", 1259))

        camera = ViscaCamera("10.0.0.1")

        with self.assertRaisesRegex(ValueError, "Invalid pan/tilt response"):
            camera.get_pan_tilt_position()


if __name__ == "__main__":
    unittest.main()
