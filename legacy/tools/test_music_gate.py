#!/usr/bin/env python3
"""Finite music, lifecycle, audio, input, logger and manual regression gate."""
import sys
import test_spot10_gate as gate
gate.LABEL = 'MUSIC_GATE'
gate.SCOPE = 'MS2 curated score/Surge asset integrity/bounded rendered playback plus directly affected regressions; native GMod audio pending'
gate.LUA = [
    'test_music_policy.lua', 'test_ms3_song_policy.lua', 'test_music_bundle.lua', 'test_music_server.lua', 'test_music_client.lua', 'test_music_options.lua', 'test_music_authorization.lua', 'test_music_native_hitch.lua',
    'test_music_transitions.lua', 'test_music_resources.lua', 'test_player_options.lua',
    'test_low_end_palette.lua', 'test_low_end_geometry.lua', 'test_low_end_options.lua',
    'test_adventure_presentation.lua', 'test_feedback_language.lua',
    'validate_spot05_die_logger.lua', 'validate_spot04_audio.lua',
    'test_warden.lua', 'test_warden_health.lua', 'test_hector_encounter.lua',
    'test_hector_health.lua', 'test_hector_presentation.lua',
    'test_deborah_finale_presentation.lua', 'test_campaign_timeout.lua',
    'test_magic_hourglass.lua', 'test_damsel_staging.lua', 'test_damsel_progression.lua',
    'test_spot17_movement_server.lua', 'test_spot17_movement_client.lua',
    'test_cross_feats_dodge.lua', 'test_native_resource_lifecycle.lua',
    'test_snapshot_delivery.lua', 'test_manual_transport.lua', 'test_spot13_unread.lua',
]
gate.EXTRA_SUITES = [('ms3_audio_bridge', ['python3','tools/test_ms3_audio_bridge.py']),
                    ('ms2_catalog', ['python3','tools/test_ms2_catalog.py']),
                    ('ms2_surge_bank', ['python3','tools/test_ms2_surge_bank.py']),
                    ('ms2_sequence', ['node','tools/test_music_sequence.js']),
                    ('ms3_sixteen_bar', ['python3','tools/test_ms3_sixteen_bar.py']),
                    ('ms3_song_score', ['python3','tools/test_ms3_song_score.py']),
                    ('ms3_song_sequence', ['node','tools/test_ms3_song_sequence.js']),
                    ('ms3_sample_clock', ['node','tools/test_ms3_transport.js']),
                    ('release_wiring', ['python3','tools/validate_release_wiring.py']),
                    ('vr_shared_startup', ['python3','tools/run_lua54.py','tools/test_vr.lua'])]
if __name__ == '__main__':
    sys.exit(gate.main())
