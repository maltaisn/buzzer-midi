#  Copyright 2021 Nicolas Maltais
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import copy
import wave
from dataclasses import dataclass
from typing import Optional, List

import numpy as np

from music_data import BuzzerMusic, BuzzerNote, BuzzerTrack, get_note_freq

# sample rate for WAV file if sample width >= 2
SAMPLE_RATE = 44100

# sample rate for WAV file if sample width = 1 (PWM mode)
PWM_SAMPLE_RATE = 524288
# number of samples in a PWM period.
# the PWM resolution is log2(PWM_PERIOD) = 3 bits
PWM_PERIOD = 16

# maximum value in a WAV file sample.
SAMPLE_MAX = 255


@dataclass
class TrackState:
    current_note: Optional[BuzzerNote]
    current_idx: int
    phase: int
    level: int
    done: bool
    note_max_phase: int
    track: BuzzerTrack

    def __init__(self, track: BuzzerTrack):
        self.track = track
        self.current_note = None
        self.current_idx = 0
        self.phase = 0
        self.level = 0
        self.done = False


def _go_to_next_note(states: List[TrackState]) -> None:
    # decrement note duration left and go to next note if needed.
    for i, state in enumerate(states):
        if state.done:
            continue
        note = state.current_note
        track = state.track
        if not note or note.duration == 0:
            if state.current_idx == len(track.notes):
                state.done = True
            else:
                note = copy.copy(track.notes[state.current_idx])
                state.current_note = note
                if note.note != BuzzerNote.NONE:
                    # timer count is an integer, rounding results in some error
                    # calculate note frequency as if it was produced by a timer.
                    # / 2 since timer interrupt is called twice per note period.
                    timer_count = round(track.spec.timer_period / get_note_freq(note.note) / 2)
                    note_freq = track.spec.timer_period / timer_count / 2
                    state.note_max_phase = SAMPLE_RATE / note_freq
                state.current_idx += 1
                state.level = 0
        else:
            note.duration -= 1


def _generate_frames_for_state(frames: np.ndarray, i: int, levels: np.ndarray,
                               frames_count: int, states: List[TrackState]) -> None:
    # generate frames for current 1/32nd of a beat.
    active_states = [state for state in states
                     if not state.done and state.current_note.note != BuzzerNote.NONE]
    for j in range(frames_count):
        level = 0
        for state in active_states:
            state.phase += 1
            if state.phase >= state.note_max_phase:
                state.phase = 0
                state.level = 1 - state.level
            level += state.level

        frames[i] = levels[level]
        i += 1


def _generate_frames_for_state_pwm(frames: np.ndarray, i: int,
                                   frames_count: int, states: List[TrackState]) -> None:
    # generate frames for current 1/32nd of a beat, in PWM.
    active_states = [state for state in states
                     if not state.done and state.current_note.note != BuzzerNote.NONE]
    level_norm = PWM_PERIOD / len(states)
    for j in range(frames_count // PWM_PERIOD):
        level = 0
        for state in active_states:
            state.phase += 1
            if state.phase >= state.note_max_phase:
                state.phase = 0
                state.level = 1 - state.level
            level += state.level
        level = round(level * level_norm)

        frames[i:i + level] = SAMPLE_MAX
        i += PWM_PERIOD


def create_wav_file(music: BuzzerMusic, filename: str,
                    sample_width: int, show_progress: bool = False) -> None:
    tracks = music.tracks

    if not (0 < sample_width <= 8):
        raise RuntimeError("sample width out of bounds")

    beat_duration = music.tempo * 256e-6 * BuzzerNote.TIMEFRAME_RESOLUTION
    sample_rate = PWM_SAMPLE_RATE if sample_width == 1 else SAMPLE_RATE

    levels = None
    if sample_width != 1:
        # quantitize SAMPLE_MAX into levels according to number of tracks and sample width
        levels_count = len(tracks) + 1
        actual_levels_count = min(levels_count, 1 << sample_width)
        levels = np.zeros(levels_count, dtype=np.uint8)
        level_step = SAMPLE_MAX / (actual_levels_count - 1)
        for i in range(levels_count):
            levels[i] = round(((SAMPLE_MAX / (levels_count - 1)) * i) / level_step) * level_step

    states = [TrackState(track) for track in tracks]
    frames_per_32nd = round(sample_rate / BuzzerNote.TIMEFRAME_RESOLUTION * beat_duration)
    frame_rate_actual = round(frames_per_32nd * BuzzerNote.TIMEFRAME_RESOLUTION / beat_duration)
    max_notes = max((sum(((note.duration + 1) for note in track.notes)) for track in tracks))
    frames = np.zeros(max_notes * frames_per_32nd, dtype=np.uint8)
    i = 0
    for k in range(max_notes):
        _go_to_next_note(states)
        if sample_width == 1:
            _generate_frames_for_state_pwm(frames, i, frames_per_32nd, states)
        else:
            _generate_frames_for_state(frames, i, levels, frames_per_32nd, states)
        i += frames_per_32nd
        if show_progress:
            print(f"Generating WAV file {(k + 1) / max_notes * 100:.0f}%\r", end="")
    if show_progress:
        print()

    wav: wave.Wave_write = wave.open(filename, "wb")
    wav.setnchannels(1)
    wav.setsampwidth(1)
    wav.setframerate(frame_rate_actual)
    wav.setnframes(len(frames))
    wav.writeframes(frames)
