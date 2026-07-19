import tempfile
import unittest

from server.playback.runtime import PlaybackRuntime
from server.websocket.events import EventHub


def make_track(position='1', title='Track', duration='0:30'):
    return {
        'title': title,
        'position': position,
        'duration': duration,
        'deck_number': 1,
        'cd_position': 1,
    }


def make_track_on_cd(cd_position, title='Track', duration='1:00'):
    track = make_track(title=title, duration=duration)
    track['cd_position'] = cd_position
    return track


class FakeSLinkClient:
    def __init__(self):
        self.sent_tracks = []
        self.sent_transport = []
        self.sent_continuous_status = []

    def send_track(self, track):
        self.sent_tracks.append(track)

    def send_pause(self, deck_number=1):
        self.sent_transport.append(('pause', deck_number))

    def send_stop(self, deck_number=1):
        self.sent_transport.append(('stop', deck_number))

    def send_next_track(self, deck_number=1):
        self.sent_transport.append(('next_track', deck_number))

    def send_previous_track(self, deck_number=1):
        self.sent_transport.append(('previous_track', deck_number))

    def send_resume(self, deck_number=1):
        self.sent_transport.append(('resume', deck_number))

    def send_enable_continuous_status(self, deck_number=1):
        self.sent_continuous_status.append(('enable', deck_number))


class FailingSLinkClient:
    def send_enable_continuous_status(self, deck_number=1):
        raise RuntimeError('S-Link offline')

    def send_track(self, track):
        raise RuntimeError('S-Link offline')


class PlaybackRuntimeTest(unittest.TestCase):
    def make_runtime(self, event_hub=None):
        fake_slink = FakeSLinkClient()
        runtime = PlaybackRuntime(fake_slink, advance_lead_seconds=0, event_hub=event_hub)
        self.addCleanup(runtime.shutdown)
        return runtime, fake_slink

    def make_runtime_with_adjacent(self, tracks):
        fake_slink = FakeSLinkClient()

        def resolver(current_track, direction):
            index = next((item_index for item_index, track in enumerate(tracks) if track['position'] == current_track['position']), None)
            if index is None:
                return None
            target_index = index + (1 if direction == 'next' else -1)
            if target_index < 0 or target_index >= len(tracks):
                return None
            return tracks[target_index]

        runtime = PlaybackRuntime(fake_slink, advance_lead_seconds=0, adjacent_track_resolver=resolver)
        self.addCleanup(runtime.shutdown)
        return runtime, fake_slink

    def test_play_track_returns_authoritative_status(self):
        runtime, fake_slink = self.make_runtime()
        track = make_track(title='First')

        status = runtime.play_track(track)

        self.assertEqual(status['current_track'], track)
        self.assertEqual(status['queue'], [track])
        self.assertEqual(status['upcoming'], [])
        self.assertEqual(status['duration'], 30)
        self.assertEqual(status['remaining'], 30)
        self.assertEqual(status['current_deck'], 1)
        self.assertEqual(status['current_cd'], 1)
        self.assertEqual(status['playback_state'], 'playing')
        self.assertIn('last_update_timestamp', status)
        self.assertEqual(fake_slink.sent_tracks, [track])
        self.assertEqual(fake_slink.sent_continuous_status, [('enable', 1)])

    def test_continuous_status_is_enabled_once_per_deck_before_playback(self):
        runtime, fake_slink = self.make_runtime()
        first = make_track(title='First')
        second = make_track(title='Second')

        runtime.play_track(first)
        runtime.play_track(second)

        self.assertEqual(fake_slink.sent_continuous_status, [('enable', 1)])

    def test_playback_start_offset_keeps_elapsed_aligned_with_hardware(self):
        fake_slink = FakeSLinkClient()
        runtime = PlaybackRuntime(fake_slink, playback_start_offset_seconds=1)
        self.addCleanup(runtime.shutdown)

        runtime.play_track(make_track(duration='1:00'))
        with runtime._lock:
            runtime._state.started_at -= 1
        status = runtime.status()

        self.assertEqual(status['elapsed'], 0)
        self.assertEqual(status['remaining'], 60)
        self.assertEqual(status['load_delay_remaining'], 0)

    def test_pause_is_soft_scheduler_pause(self):
        runtime, fake_slink = self.make_runtime()
        track = make_track()
        runtime.play_track(track)

        status = runtime.pause()

        self.assertEqual(status['playback_state'], 'paused')
        self.assertEqual(fake_slink.sent_tracks, [track])
        self.assertEqual(fake_slink.sent_transport, [('pause', 1)])

    def test_stop_sends_physical_transport_command(self):
        runtime, fake_slink = self.make_runtime()
        runtime.play_track(make_track())

        status = runtime.stop()

        self.assertEqual(status['playback_state'], 'stopped')
        self.assertEqual(status['current_track']['title'], 'Track')
        self.assertEqual(fake_slink.sent_transport, [('stop', 1)])

    def test_stop_resets_progress_to_start_but_keeps_current_track_display(self):
        runtime, _ = self.make_runtime()
        runtime.play_track(make_track(duration='1:00'))
        with runtime._lock:
            runtime._state.started_at -= 20

        status = runtime.stop(send_hardware=False)

        self.assertEqual(status['playback_state'], 'stopped')
        self.assertEqual(status['current_track']['title'], 'Track')
        self.assertEqual(status['elapsed'], 0)
        self.assertEqual(status['remaining'], 60)
        self.assertEqual(status['progress'], 0)

    def test_persistence_restores_last_track_without_claiming_playing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence_path = f'{temp_dir}/playback_state.json'
            runtime = PlaybackRuntime(FakeSLinkClient(), persistence_path=persistence_path)
            self.addCleanup(runtime.shutdown)
            runtime.play_track(make_track(title='Persisted', duration='1:00'))

            restored = PlaybackRuntime(FakeSLinkClient(), persistence_path=persistence_path)
            self.addCleanup(restored.shutdown)
            status = restored.status()

            self.assertEqual(status['playback_state'], 'stopped')
            self.assertEqual(status['current_track']['title'], 'Persisted')
            self.assertEqual(status['duration'], 60)

    def test_transport_command_uses_current_deck_number(self):
        runtime, fake_slink = self.make_runtime()
        track = make_track()
        track['deck_number'] = '2'
        runtime.play_track(track)

        runtime.pause()

        self.assertEqual(fake_slink.sent_transport, [('pause', 2)])

    def test_observed_pause_and_stop_do_not_echo_transport_commands(self):
        runtime, fake_slink = self.make_runtime()
        runtime.play_track(make_track())

        pause_status = runtime.handle_transport_status('PAUSE')
        stop_status = runtime.handle_transport_status('STOP')

        self.assertEqual(pause_status['playback_state'], 'paused')
        self.assertEqual(stop_status['playback_state'], 'stopped')
        self.assertEqual(fake_slink.sent_transport, [])

    def test_resume_from_stopped_known_track_restarts_runtime_progress(self):
        runtime, fake_slink = self.make_runtime()
        runtime.play_track(make_track(duration='1:00'))
        runtime.stop(send_hardware=False)
        with runtime._lock:
            runtime._state.elapsed = 6
            runtime._state.paused_elapsed = 6

        status = runtime.resume()

        self.assertEqual(status['playback_state'], 'playing')
        self.assertEqual(status['elapsed'], 6)
        self.assertEqual(status['remaining'], 54)
        self.assertEqual(status['progress'], 10)
        self.assertEqual(fake_slink.sent_transport, [('resume', 1)])

    def test_observed_play_from_stopped_known_track_restarts_runtime_without_echo(self):
        runtime, fake_slink = self.make_runtime()
        runtime.play_track(make_track(duration='1:00'))
        runtime.stop(send_hardware=False)

        status = runtime.handle_transport_status('PLAY')

        self.assertEqual(status['playback_state'], 'playing')
        self.assertEqual(fake_slink.sent_transport, [])

    def test_observed_next_advances_queue_without_sending_track_command(self):
        runtime, fake_slink = self.make_runtime()
        first = make_track(position='1', title='First')
        second = make_track(position='2', title='Second')
        runtime.play_playlist({'name': 'Queue', 'tracks': [first, second]})

        status = runtime.handle_transport_status('NEXT_TRACK')

        self.assertEqual(status['current_track'], second)
        self.assertEqual(fake_slink.sent_tracks, [first])
        self.assertEqual(fake_slink.sent_transport, [])

    def test_observed_previous_moves_back_in_queue_without_sending_track_command(self):
        runtime, fake_slink = self.make_runtime()
        first = make_track(position='1', title='First')
        second = make_track(position='2', title='Second')
        runtime.play_playlist({'name': 'Queue', 'tracks': [first, second]})
        runtime.handle_transport_status('NEXT_TRACK')

        status = runtime.handle_transport_status('PREV_TRACK')

        self.assertEqual(status['current_track'], first)
        self.assertEqual(status['upcoming'], [second])
        self.assertEqual(fake_slink.sent_tracks, [first])
        self.assertEqual(fake_slink.sent_transport, [])

    def test_next_and_previous_resolve_adjacent_release_track_without_playlist_queue(self):
        first = make_track(position='1', title='First')
        second = make_track(position='2', title='Second')
        runtime, fake_slink = self.make_runtime_with_adjacent([first, second])
        runtime.play_track(first)

        next_status = runtime.next_track()
        previous_status = runtime.previous_track()

        self.assertEqual(next_status['current_track']['title'], 'Second')
        self.assertEqual(next_status['progress'], 0)
        self.assertEqual(previous_status['current_track']['title'], 'First')
        self.assertEqual(fake_slink.sent_transport, [('next_track', 1)])
        self.assertEqual(fake_slink.sent_tracks, [first, first])

    def test_previous_track_sends_absolute_track_command_when_target_is_known(self):
        runtime, fake_slink = self.make_runtime()
        first = make_track(position='1', title='First')
        second = make_track(position='2', title='Second')
        runtime.play_playlist({'name': 'Queue', 'tracks': [first, second]})
        runtime.handle_transport_status('NEXT_TRACK')

        status = runtime.previous_track()

        self.assertEqual(status['current_track'], first)
        self.assertEqual(fake_slink.sent_tracks, [first, first])
        self.assertEqual(fake_slink.sent_transport, [])

    def test_status_normalizes_stale_static_progress(self):
        runtime, _ = self.make_runtime()
        runtime.play_track(make_track(duration='3:26'))
        runtime.stop(send_hardware=False)
        with runtime._lock:
            runtime._state.elapsed = 6
            runtime._state.remaining = 0
            runtime._state.progress = 100

        status = runtime.status()

        self.assertEqual(status['elapsed'], 6)
        self.assertEqual(status['remaining'], 200)
        self.assertEqual(status['progress'], 2.91)

    def test_observed_track_from_hardware_updates_current_track_without_sending_command(self):
        runtime, fake_slink = self.make_runtime()
        first = make_track(position='1', title='First')
        second = make_track(position='2', title='Second')
        runtime.play_track(first)

        status = runtime.observe_track(second)

        self.assertEqual(status['current_track'], second)
        self.assertEqual(status['queue'], [second])
        self.assertEqual(status['playback_state'], 'playing')
        self.assertEqual(fake_slink.sent_tracks, [first])

    def test_observed_track_inside_existing_playlist_moves_current_index(self):
        runtime, fake_slink = self.make_runtime()
        first = make_track(position='1', title='First')
        second = make_track(position='2', title='Second')
        third = make_track(position='3', title='Third')
        runtime.play_playlist({'name': 'Queue', 'tracks': [first, second, third]})

        status = runtime.observe_track(second)

        self.assertEqual(status['current_track'], second)
        self.assertEqual(status['upcoming'], [third])
        self.assertEqual(fake_slink.sent_tracks, [first])

    def test_next_track_in_synchronizes_remaining_time_for_scheduler(self):
        event_hub = EventHub()
        events = []
        event_hub.subscribe(lambda event_type, payload: events.append((event_type, payload['remaining'])))
        runtime, _ = self.make_runtime(event_hub)
        runtime.play_track(make_track(duration='1:00'))

        status = runtime.handle_transport_status('NEXT_TRACK_IN', {'duration': '27'})

        self.assertEqual(status['remaining'], 27)
        self.assertEqual(status['elapsed'], 33)
        self.assertEqual(status['load_delay_remaining'], 0)
        self.assertIn(('progress_tick', 27), events)

    def test_next_track_in_allows_scheduler_to_advance_when_inside_lead_time(self):
        runtime, fake_slink = self.make_runtime()
        runtime.advance_lead_seconds = 3
        first = make_track(position='1', title='First', duration='1:00')
        second = make_track(position='2', title='Second', duration='0:30')
        runtime.play_playlist({'name': 'Queue', 'tracks': [first, second]})

        runtime.handle_transport_status('NEXT_TRACK_IN', {'duration': '3'})
        runtime._scheduler.tick()
        status = runtime.status()

        self.assertEqual(status['current_track'], second)
        self.assertEqual(fake_slink.sent_tracks, [first, second])

    def test_advance_starts_next_track(self):
        runtime, fake_slink = self.make_runtime()
        first = make_track(position='1', title='First')
        second = make_track(position='2', title='Second')
        runtime.play_playlist({'name': 'Queue', 'tracks': [first, second]})

        with runtime._lock:
            runtime._advance_locked()
            status = runtime.status_locked()

        self.assertEqual(status['current_track'], second)
        self.assertEqual(status['upcoming'], [])
        self.assertEqual(fake_slink.sent_tracks, [first, second])

    def test_scheduler_tick_advances_after_duration_without_frontend_event(self):
        runtime, fake_slink = self.make_runtime()
        first = make_track(position='1', title='First', duration='0:01')
        second = make_track(position='2', title='Second', duration='0:30')
        runtime.play_playlist({'name': 'Queue', 'tracks': [first, second]})

        with runtime._lock:
            runtime._state.started_at -= 2
        runtime._scheduler.tick()
        status = runtime.status()

        self.assertEqual(status['current_track'], second)
        self.assertEqual(status['duration'], 30)
        self.assertEqual(fake_slink.sent_tracks, [first, second])

    def test_scheduler_continues_across_three_tracks_without_transport_events(self):
        runtime, fake_slink = self.make_runtime()
        first = make_track(position='1', title='First', duration='0:01')
        second = make_track(position='2', title='Second', duration='0:01')
        third = make_track(position='3', title='Third', duration='0:30')
        runtime.play_playlist({'name': 'Queue', 'tracks': [first, second, third]})

        with runtime._lock:
            runtime._state.started_at -= 2
        runtime._scheduler.tick()

        with runtime._lock:
            runtime._state.started_at -= 2
        runtime._scheduler.tick()
        status = runtime.status()

        self.assertEqual(status['current_track'], third)
        self.assertEqual(status['upcoming'], [])
        self.assertEqual([track['title'] for track in fake_slink.sent_tracks], ['First', 'Second', 'Third'])

    def test_different_cd_load_delay_holds_elapsed_at_zero_until_audio_start(self):
        fake_slink = FakeSLinkClient()
        runtime = PlaybackRuntime(
            fake_slink,
            advance_lead_seconds=0,
            changer_load_base_seconds=4,
            changer_load_seconds_per_slot=0.5,
            changer_load_max_seconds=35,
            playback_start_offset_seconds=1,
        )
        self.addCleanup(runtime.shutdown)

        first = make_track_on_cd(1, title='First')
        second = make_track_on_cd(41, title='Second')
        runtime.play_track(first)
        status = runtime.play_track(second)

        self.assertEqual(status['load_delay_seconds'], 24)
        self.assertEqual(status['elapsed'], 0)
        self.assertEqual(status['remaining'], 60)

        with runtime._lock:
            runtime._state.started_at -= status['load_delay_seconds'] + runtime.playback_start_offset_seconds + 30
        status = runtime.status()

        self.assertEqual(status['elapsed'], 30)
        self.assertEqual(status['remaining'], 30)

    def test_same_cd_has_no_mechanical_load_delay(self):
        fake_slink = FakeSLinkClient()
        runtime = PlaybackRuntime(fake_slink, changer_load_base_seconds=4, changer_load_seconds_per_slot=0.5)
        self.addCleanup(runtime.shutdown)

        runtime.play_track(make_track_on_cd(10, title='First'))
        status = runtime.play_track(make_track_on_cd(10, title='Second'))

        self.assertEqual(status['load_delay_seconds'], 0)

    def test_runtime_publishes_state_events(self):
        event_hub = EventHub()
        events = []
        event_hub.subscribe(lambda event_type, payload: events.append((event_type, payload['playback_state'])))
        runtime, _ = self.make_runtime(event_hub)

        runtime.play_track(make_track())
        runtime._scheduler.tick()
        runtime.pause()
        runtime.stop()

        self.assertIn(('queue_changed', 'playing'), events)
        self.assertIn(('playback_started', 'playing'), events)
        self.assertIn(('progress_tick', 'playing'), events)
        self.assertIn(('playback_paused', 'paused'), events)
        self.assertIn(('playback_stopped', 'stopped'), events)

    def test_slink_failure_sets_error_state_and_publishes_event(self):
        event_hub = EventHub()
        events = []
        event_hub.subscribe(lambda event_type, payload: events.append((event_type, payload['playback_state'])))
        runtime = PlaybackRuntime(FailingSLinkClient(), event_hub=event_hub)
        self.addCleanup(runtime.shutdown)

        with self.assertRaises(RuntimeError):
            runtime.play_track(make_track())

        status = runtime.status()
        self.assertEqual(status['playback_state'], 'error')
        self.assertEqual(status['error'], 'S-Link offline')
        self.assertIn(('playback_error', 'error'), events)

    def test_invalid_duration_metadata_sets_error_state(self):
        event_hub = EventHub()
        events = []
        event_hub.subscribe(lambda event_type, payload: events.append((event_type, payload['playback_state'])))
        runtime, _ = self.make_runtime(event_hub)

        with self.assertRaises(ValueError):
            runtime.play_track(make_track(duration='bad'))

        status = runtime.status()
        self.assertEqual(status['playback_state'], 'error')
        self.assertEqual(status['error'], 'Unsupported duration format: bad')
        self.assertIn(('playback_error', 'error'), events)


if __name__ == '__main__':
    unittest.main()