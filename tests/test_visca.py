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
        mock_socket.settimeout.assert_called_once()
        # send_with_response recomputes the remaining budget against a
        # deadline, so it'll be a hair under the full timeout, not exactly it.
        self.assertAlmostEqual(mock_socket.settimeout.call_args[0][0], 1.0, delta=0.05)

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

    @patch("visca.time.sleep")
    @patch("visca.socket.socket")
    def test_send_with_response_skips_stale_ack_datagrams(self, mock_socket_factory, _mock_sleep):
        # A leftover ACK (3 bytes) from an earlier fire-and-forget command
        # sitting in the socket ahead of the real inquiry reply.
        mock_socket = MagicMock()
        mock_socket_factory.return_value = mock_socket
        mock_socket.recvfrom.side_effect = [
            (b"\x90\x41\xff", ("10.0.0.1", 1259)),
            (b"\x90\x50\x00\x00\x00\x01\xff", ("10.0.0.1", 1259)),
        ]

        camera = ViscaCamera("10.0.0.1")
        response = camera.send_with_response("81 09 04 47 FF")

        self.assertEqual(response, b"\x90\x50\x00\x00\x00\x01\xff")
        self.assertEqual(mock_socket.recvfrom.call_count, 2)

    @patch("visca.time.sleep")
    @patch("visca.socket.socket")
    def test_send_with_response_times_out_if_nothing_but_junk_arrives(self, mock_socket_factory, _mock_sleep):
        mock_socket = MagicMock()
        mock_socket_factory.return_value = mock_socket
        mock_socket.recvfrom.return_value = (b"\x90\x41\xff", ("10.0.0.1", 1259))

        camera = ViscaCamera("10.0.0.1", timeout=0.05)

        with self.assertRaises(TimeoutError):
            camera.send_with_response("81 09 04 47 FF")

    @patch("visca.time.sleep")
    @patch("visca.socket.socket")
    def test_set_pan_tilt_position_sends_absolute_position_command(self, mock_socket_factory, _mock_sleep):
        mock_socket = MagicMock()
        mock_socket_factory.return_value = mock_socket

        camera = ViscaCamera("10.0.0.1")
        camera.set_pan_tilt_position(0x1234, 0x00FF, pan_speed=10, tilt_speed=5)

        sent_bytes = mock_socket.sendto.call_args[0][0]
        self.assertEqual(sent_bytes, bytes.fromhex("81 01 06 02 0A 05 01 02 03 04 00 00 0F 0F FF"))

    @patch("visca.time.sleep")
    @patch("visca.socket.socket")
    def test_set_zoom_position_sends_direct_zoom_command(self, mock_socket_factory, _mock_sleep):
        mock_socket = MagicMock()
        mock_socket_factory.return_value = mock_socket

        camera = ViscaCamera("10.0.0.1")
        camera.set_zoom_position(0x0384)

        sent_bytes = mock_socket.sendto.call_args[0][0]
        self.assertEqual(sent_bytes, bytes.fromhex("81 01 04 47 00 03 08 04 FF"))

    @patch("visca.time.sleep")
    @patch("visca.socket.socket")
    def test_move_to_position_sends_pan_tilt_then_zoom(self, mock_socket_factory, _mock_sleep):
        mock_socket = MagicMock()
        mock_socket_factory.return_value = mock_socket

        camera = ViscaCamera("10.0.0.1")
        camera.move_to_position(1, 2, 3, pan_speed=9, tilt_speed=6)

        self.assertEqual(mock_socket.sendto.call_count, 2)

    def test_encode_decode_position_nibbles_round_trip(self):
        for value in (0, 1, 255, 4096, 65535, -1, -100):
            nibbles = ViscaCamera._encode_position_nibbles(value)
            decoded = ViscaCamera._decode_position_nibbles([int(n[1], 16) for n in nibbles])
            self.assertEqual(decoded, value & 0xFFFF)

    def test_set_target_updates_address_without_new_socket(self):
        camera = ViscaCamera("10.0.0.1", port=1259)
        original_sock = camera.sock

        camera.set_target("192.168.1.50", 5555)

        self.assertEqual(camera.addr, ("192.168.1.50", 5555))
        self.assertIs(camera.sock, original_sock)

        camera.set_target("192.168.1.60")
        self.assertEqual(camera.addr, ("192.168.1.60", 5555))


if __name__ == "__main__":
    unittest.main()
