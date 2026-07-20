import unittest
from unittest.mock import Mock, patch

from server.sony.slink import SLinkClient, build_playlist_command, build_track_command, build_transport_command, duration_to_seconds


class SLinkTest(unittest.TestCase):
    def test_duration_to_seconds_defaults_empty_duration(self):
        self.assertEqual(duration_to_seconds(''), 200)
        self.assertEqual(duration_to_seconds('5:21'), 321)
        self.assertEqual(duration_to_seconds('1:02:03'), 3723)

    def test_duration_to_seconds_rejects_unsupported_duration(self):
        with self.assertRaisesRegex(ValueError, 'Unsupported duration format: bad'):
            duration_to_seconds('bad')

    def test_build_track_command_for_deck_one_under_100(self):
        command = build_track_command({'deck_number': 1, 'cd_position': 9, 'position': '2'})

        self.assertEqual(command, '90500902\r\n')

    def test_build_track_command_for_deck_two_100_to_200(self):
        command = build_track_command({'deck_number': 2, 'cd_position': 100, 'position': '1-03'})

        self.assertEqual(command, '92509a03\r\n')

    def test_build_track_command_for_position_above_200(self):
        command = build_track_command({'deck_number': 1, 'cd_position': 201, 'position': '4'})

        self.assertEqual(command, '93500104\r\n')

    def test_build_playlist_command_includes_duration_seconds(self):
        command = build_playlist_command({
            'tracks': [
                {'deck_number': 1, 'cd_position': 9, 'position': '2', 'duration': '5:21'},
            ]
        })

        self.assertEqual(command, 'PLAYLIST\r\n90500902:321\r\n')

    def test_build_transport_commands(self):
        self.assertEqual(build_transport_command(1), '9001\r\n')
        self.assertEqual(build_transport_command(2), '9002\r\n')
        self.assertEqual(build_transport_command(8, deck_number=2), '9208\r\n')
        self.assertEqual(build_transport_command(25), '9025\r\n')
        self.assertEqual(build_transport_command(26), '9026\r\n')

    def test_transport_methods_send_raw_slink_commands(self):
        client = SLinkClient('http://esp32.local:8080')
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {'webhook_url': 'http://192.168.1.57:5000/webhook'}

        with patch('server.sony.slink.requests.post', return_value=response) as post:
            client.send_stop()
            client.send_pause()
            client.send_next_track(deck_number=2)
            client.send_enable_continuous_status()

        self.assertEqual(post.call_args_list[0].args, ('http://esp32.local:8080',))
        self.assertEqual(post.call_args_list[0].kwargs['data'], '9001\r\n')
        self.assertEqual(post.call_args_list[1].kwargs['data'], '9002\r\n')
        self.assertEqual(post.call_args_list[2].kwargs['data'], '9208\r\n')
        self.assertEqual(post.call_args_list[3].kwargs['data'], '9025\r\n')

    def test_configure_webhook_target_posts_discovered_backend_url_to_esp32(self):
        client = SLinkClient('http://esp32.local:8080')
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {'webhook_url': 'http://192.168.1.57:5000/webhook'}

        with patch.object(client, '_local_ip_for_server', return_value='192.168.1.57'), \
                patch('server.sony.slink.requests.post', return_value=response) as post:
            client.configure_webhook_target()

        self.assertEqual(post.call_args.args, ('http://esp32.local:8080/webhook-target',))
        self.assertEqual(post.call_args.kwargs['json'], {'webhook_url': 'http://192.168.1.57:5000/webhook'})
        self.assertEqual(post.call_args.kwargs['timeout'], 3)

    def test_configure_webhook_target_rejects_legacy_esp32_ok_response(self):
        client = SLinkClient('http://esp32.local:8080')
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.side_effect = ValueError('not json')

        with patch.object(client, '_local_ip_for_server', return_value='192.168.1.57'), \
                patch('server.sony.slink.requests.post', return_value=response), \
                self.assertRaisesRegex(RuntimeError, 'flash updated firmware'):
            client.configure_webhook_target()


if __name__ == '__main__':
    unittest.main()