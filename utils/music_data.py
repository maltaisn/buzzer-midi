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

from dataclasses import dataclass, field
from typing import List

FramesNotes = List[List[List[int]]]


def get_note_freq(note: int) -> float:
    """Return the frequency of a note value in Hz (C2=0)."""
    return 440 * 2**((note - 33) / 12)


@dataclass
class ChannelSpec:
    note_range: range
    timer_period: int = field(default=0)


@dataclass
class BuzzerNote:
    # note as encoded in buzzer busic, C2 is 0, B7 is 71
    note: int
    # duration, 0-MAX_DURATION (0 being 1/32nd of a beat)
    duration: int

    NONE = 0xff
    MAX_DURATION = 0x7fff
    MAX_NOTE = 83  # B8

    # minimum note resolution for buzzer music system (1/32nd of a beat).
    TIMEFRAME_RESOLUTION = 32

    def encode(self) -> bytearray:
        b = bytearray()
        b.append(self.note)
        if self.duration >= 0x8000:
            raise ValueError("Note duration cannot be encoded")
        elif self.duration >= 0x80:
            b.append((self.duration & 0x7f) | 0x80)
            b.append(self.duration >> 7)
        else:
            b.append(self.duration)
        return b

    @staticmethod
    def from_midi(midi_note: int):
        # C2=36 in MIDI, C2=0 in buzzer music
        return midi_note - 36


@dataclass
class BuzzerTrack:
    # track number, 0 to MAX_TRACK-1
    number: int
    # track note range
    spec: ChannelSpec
    # track notes
    notes: List[BuzzerNote]

    def __init__(self, number: int, spec: ChannelSpec):
        self.number = number
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

    def encode(self) -> bytearray:
        b = bytearray()
        b.append(self.number)
        b += b"\x00\x00"
        for note in self.notes:
            b += note.encode()
        b += b'\xfe'  # end byte
        if len(b) > 0xffff:
            raise RuntimeError(f"Track is too long to be encoded ({len(b)} bytes)")
        b[1:3] = len(b).to_bytes(2, "little", signed=False)
        return b


@dataclass
class BuzzerMusic:
    tempo: int
    tracks: List[BuzzerTrack] = field(default_factory=list)

    # encodeable tempo bounds
    TEMPO_MIN = round(256 * 8192)
    TEMPO_MAX = round(1 * 8192)

    def encode(self) -> bytearray:
        if len(set(t.number for t in self.tracks)) != len(self.tracks):
            raise RuntimeError("tracks must be unique")

        b = bytearray()
        b += self.tempo.to_bytes(1, "little", signed=False)
        if self.tracks:
            for track in self.tracks:
                if len(track.notes) > 1 or len(track.notes) != 0 and \
                        track.notes[0].note != BuzzerNote.NONE:
                    b += track.encode()
        else:
            # no tracks, put single empty track
            b += BuzzerTrack(0, ChannelSpec(range(0), 0)).encode()
        return b

    @staticmethod
    def encode_beat_us_tempo(us: float) -> int:
        return round(us / 8192) - 1
