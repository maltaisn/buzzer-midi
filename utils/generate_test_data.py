#!/usr/bin/env python3

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

# generate test data for 6 tracks.
# intended for atmega328p target but will also work with atmega3208.

import random
from typing import List, Iterable

from midi_convert import write_c_header
from music_data import BuzzerTrack, BuzzerMusic, BuzzerNote, ChannelSpec

# test data file name
filename = "../include/music_data.h"

channels_spec = [
    ChannelSpec(range(11, 62)),
    ChannelSpec(range(11, 62)),
    ChannelSpec(range(0, 73)),
    ChannelSpec(range(0, 73)),
    ChannelSpec(range(23, 73)),
    ChannelSpec(range(23, 73)),
]

def add_pause(tracks: List[BuzzerTrack], duration: int) -> None:
    for i in range(duration):
        for track in tracks:
            track.add_note(BuzzerNote.NONE)


def play_note_on_tracks(tracks: List[BuzzerTrack], nums: Iterable[int],
                        note: int = 24, duration: int = 128) -> None:
    """play a note on tracks by number, for a duration, while other tracks are silent."""
    for track in tracks:
        for j in range(duration):
            track.add_note(note if track.number in nums else BuzzerNote.NONE)


def main() -> None:
    music = BuzzerMusic(60)  # 120 BPM
    tracks = [BuzzerTrack(i, spec) for i, spec in enumerate(channels_spec)]
    music.tracks = tracks

    # play_note_on_tracks(tracks, [0], duration=32768)

    # test each buzzer separatedly
    add_pause(tracks, 32)
    play_note_on_tracks(tracks, [0, 1])
    add_pause(tracks, 32)
    play_note_on_tracks(tracks, [2, 3])
    add_pause(tracks, 32)
    play_note_on_tracks(tracks, [4, 5])

    # test all buzzers A/B channels
    add_pause(tracks, 32)
    play_note_on_tracks(tracks, [0, 2, 4])
    add_pause(tracks, 32)
    play_note_on_tracks(tracks, [1, 3, 5])

    # play all buzzers at once a few times
    add_pause(tracks, 32)
    play_note_on_tracks(tracks, [0, 1, 2, 3, 4, 5])

    # play 32nd second notes over full range on each buzzer
    add_pause(tracks, 32)
    for i, track in enumerate(tracks):
        for bnote in track.spec.note_range:
            play_note_on_tracks(tracks, [i], note=bnote, duration=8)

    # quick notes on buzzer
    add_pause(tracks, 16)
    for i in range(len(tracks)):
        add_pause(tracks, 16)
        for _ in range(16):
            play_note_on_tracks(tracks, [1], note=60 - 6 * i, duration=4)
            add_pause(tracks, 1)

    # random notes, random buzzers
    add_pause(tracks, 32)
    for _ in range(10):
        nums = set(random.choices(range(6), k=random.randint(1, 6)))
        for i in range(16):
            for i, track in enumerate(tracks):
                note = random.choice(track.spec.note_range)
                track.add_note(note if track.number in nums else BuzzerNote.NONE)

    # finalize tracks and encode
    for track in tracks:
        track.finalize()
    data = music.encode()

    fd = open(filename, "w")
    print(f"test data output to {filename} ({len(data)} bytes)")
    write_c_header(fd, data, "music_data")
    fd.close()


if __name__ == "__main__":
    main()
