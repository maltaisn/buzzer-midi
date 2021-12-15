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
from collections import Counter
from dataclasses import dataclass, field
from typing import List

FramesNotes = List[List[List[int]]]


def get_note_freq(note: int) -> float:
    """Return the frequency of a note value in Hz (C2=0)."""
    return 440 * 2 ** ((note - 33) / 12)


@dataclass
class ChannelSpec:
    note_range: range
    timer_period: int = field(default=0)


@dataclass
class BuzzerNote:
    # note as encoded in buzzer busic, C2 is 0, B7 is 71
    note: int
    # duration, 0-MAX_DURATION (0 being 1/16th of a beat)
    duration: int

    NONE = 0x54
    MAX_DURATION = 0x3fff
    MAX_DURATION_REPEAT = 0x40
    MAX_NOTE = 0x53

    IMMEDIATE_PAUSE_OFFSET = 0x55
    SHORT_PAUSE_OFFSET = 0xaa

    # minimum note resolution for buzzer music system (1/16th of a beat).
    TIMEFRAME_RESOLUTION = 16

    def encode_duration(self) -> bytes:
        """Encode the duration of a note in one or two bytes."""
        b = bytearray()
        if self.duration < 128:
            b.append(self.duration)
        elif self.duration <= BuzzerNote.MAX_DURATION:
            b.append((self.duration >> 8) | 0xc0)
            b.append(self.duration & 0xff)
        else:
            raise ValueError("cannot encode duration")
        return b

    @staticmethod
    def from_midi(midi_note: int):
        # C2=36 in MIDI, C2=0 in buzzer music
        return midi_note - 36


@dataclass
class BuzzerTrack:
    # channel number
    channel: int
    # track note range
    spec: ChannelSpec
    # track notes
    notes: List[BuzzerNote]

    TRACK_NOTES_END = 0xff

    def __init__(self, number: int, spec: ChannelSpec):
        self.channel = number
        self.spec = spec
        self.notes = []

    def add_note(self, note: int) -> None:
        """append note at the end of track, merge with previous note if identical"""
        if note != BuzzerNote.NONE and note not in self.spec.note_range:
            raise ValueError("Note out of range for track")
        if len(self.notes) > 0 and self.notes[-1].note == note and \
                self.notes[-1].duration < BuzzerNote.MAX_DURATION:
            self.notes[-1].duration += 1
        else:
            # different note, or previous note exceeded max duration.
            self.notes.append(BuzzerNote(note, 0))

    def finalize(self) -> None:
        """do final modifications on track notes"""
        # remove last 'none' notes if any
        while len(self.notes) > 0 and self.notes[-1].note == BuzzerNote.NONE:
            del self.notes[-1]

    def encode(self) -> bytes:
        b = bytearray()
        durations = bytearray()
        last_duration = -1
        duration_repeat = 0
        b.append(self.channel)
        b += b"\x00\x00"  # track length
        b += b"\x00\x00"  # duration array offset (to 1st byte of track)

        # find most common pause duration shorter than 256 for track and store it
        # it will be used for notes using the immediate pause encoding.
        immediate_pause = -1
        b.append(0)
        if self.notes:
            pause_durations = (note.duration for note in self.notes
                               if note.note == BuzzerNote.NONE and note.duration <= 0xff)
            most_common_pauses = Counter(pause_durations).most_common()
            if most_common_pauses:
                immediate_pause = most_common_pauses[0][0]
                b[-1] = immediate_pause

        def end_duration_repeat() -> None:
            nonlocal duration_repeat
            if duration_repeat > 0:
                durations.append(0x80 | (duration_repeat - 1))
                duration_repeat = 0

        for note in self.notes:
            # append note byte
            if note.note == BuzzerNote.NONE:
                if note.duration == immediate_pause:
                    # note in range [0x55, 0xa8] indicate that note is followed by a pause.
                    b[-1] += BuzzerNote.IMMEDIATE_PAUSE_OFFSET
                    continue
                elif note.duration <= (0xff - BuzzerNote.SHORT_PAUSE_OFFSET):
                    # note in range [0xaa, 0xfe] indicate a pause of duration (note - 170).
                    b.append(note.duration + BuzzerNote.SHORT_PAUSE_OFFSET)
                    continue
                elif 128 < note.duration <= 129 + immediate_pause and immediate_pause <= 128:
                    # [0xaa, 0xaa]
                    # will almost never happen but if pause is in a narrow duration range
                    # it can be encoded on 2 bytes instead of 3 by combining with immediate pause
                    b.append(BuzzerNote.NONE + BuzzerNote.IMMEDIATE_PAUSE_OFFSET)
                    note = BuzzerNote(note.note, note.duration - immediate_pause - 1)
                else:
                    # [0x00, 0x54]: normal note
                    b.append(BuzzerNote.NONE)
            else:
                # note in range [0, 84[ indicate only a note.
                b.append(note.note)

            # append duration
            if note.duration == last_duration:
                # same duration as last note, use repeated duration encoding
                if duration_repeat == BuzzerNote.MAX_DURATION_REPEAT:
                    end_duration_repeat()
                duration_repeat += 1
            else:
                end_duration_repeat()
                durations += note.encode_duration()
                last_duration = note.duration

        end_duration_repeat()

        b.append(BuzzerTrack.TRACK_NOTES_END)

        b[3:5] = len(b).to_bytes(2, "little", signed=False)
        b += durations
        if len(b) > 0xffff:
            raise RuntimeError(f"track is too long to be encoded ({len(b)} bytes)")
        b[1:3] = len(b).to_bytes(2, "little", signed=False)
        return b


@dataclass
class BuzzerMusic:
    tempo: int
    tracks: List[BuzzerTrack] = field(default_factory=list)

    MUSIC_END = 0xff

    # encodeable tempo bounds
    TEMPO_MIN = round(256 * 256 * BuzzerNote.TIMEFRAME_RESOLUTION)
    TEMPO_MAX = round(1 * 256 * BuzzerNote.TIMEFRAME_RESOLUTION)

    def encode(self) -> bytes:
        if len(set(t.channel for t in self.tracks)) != len(self.tracks):
            raise RuntimeError("tracks must be unique")

        b = bytearray()
        b += self.tempo.to_bytes(1, "little", signed=False)
        for track in self.tracks:
            if len(track.notes) > 0:
                b += track.encode()
        b.append(BuzzerMusic.MUSIC_END)
        return b

    @staticmethod
    def encode_beat_us_tempo(us: float) -> int:
        return round(us / (256 * BuzzerNote.TIMEFRAME_RESOLUTION)) - 1
