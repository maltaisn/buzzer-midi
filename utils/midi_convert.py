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

# Utility to convert MIDI file to format supported by the buzzer music software.
# The format is described in include/music_data.h
#
# Usage:
# $ ./midi_convert.py <input file> <output file> [options]
# $ ./midi_convert.py <input file> - [options] > output.dat
# $ ./midi_convert.py --help

# TODO: insert short pause for repeating notes

import argparse
import math
import os
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Dict, Tuple, TextIO, Optional, NoReturn

from mido import MidiFile

from logger import LogLevel, Logger
from music_data import BuzzerMusic, BuzzerTrack, BuzzerNote
from track_strategy import AutoTrackStrategy, OptimizeSizeTrackStrategy, \
    OptimizeBuzzerTrackStrategy, ClosestTrackStrategy, ClosestAverageTrackStrategy, \
    FirstFitTrackStrategy, RandomTrackStrategy, FramesNotes, TrackStrategy, TrackStrategyFailError
from tracks_to_wav import create_wav_file

# Additional configuration parameters
# =============================

# whether to round delta times to 1 MIDI clock tick (1/24th of a beat)
# can avoid needing too many tracks when note goes off slightly after next note goes on.
round_delta_time = False

# =============================

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

TRACK_STRATEGIES: Dict[str, TrackStrategy] = {
    "auto": AutoTrackStrategy(),
    "opt_size": OptimizeSizeTrackStrategy(),
    "opt_buzzer": OptimizeBuzzerTrackStrategy(),
    "closest": ClosestTrackStrategy(),
    "closest_avg": ClosestAverageTrackStrategy(),
    "first_fit_pref": FirstFitTrackStrategy(True),
    "first_fit": FirstFitTrackStrategy(False),
    "random": RandomTrackStrategy(),
}

MidiEventMap = Dict[int, List[Tuple[int, any]]]
MidiTempoMap = Dict[int, int]

parser = argparse.ArgumentParser(description="Convert MIDI file to buzzer music format",
                                 formatter_class=argparse.RawTextHelpFormatter)
parser.add_argument("input_file", type=str, help="Input MIDI file")
parser.add_argument("output_file", type=str, default="-", nargs="?",
                    help="Output buzzer music data (- for stdout)")
parser.add_argument("-l", "--log", type=str, help="Log level (error | warning | info)",
                    choices=[v.name.lower() for v in LogLevel],
                    default=LogLevel.INFO.name.lower(), dest="log_level")
parser.add_argument("-s", "--strategy", type=str,
                    help=
                    "Track note assignment strategy:\n"
                    "- auto: try strategies in order and use first that succeeds (default)\n"
                    "- opt_size: try all strategies and choose the smallest output size\n"
                    "- opt_buzzer: try all strategies and choose the smallest number of channels\n"
                    "- closest: assign notes to track currently playing closest note\n"
                    "- closest_avg: assign notes to track with the closest average note\n"
                    "- first_fit: assign note to first track that can play it\n"
                    "- first_fit_pref: like first_fit, priorizing tracks with a smaller range\n"
                    "- random: assign notes randomly to all available tracks",
                    choices=TRACK_STRATEGIES.keys(),
                    default="auto", dest="track_strategy")
parser.add_argument("-t", "--tempo", type=int, help="Tempo override in BPM", dest="tempo")
parser.add_argument("-m", "--merge-tracks", action="store_true",
                    help="Merge MIDI tracks when creating buzzer tracks",
                    dest="merge_midi_tracks")
parser.add_argument("-x", "--header", type=str,
                    help="Name of array to output in xxd style C header (otherwise binary)",
                    dest="header_name", default=None)
parser.add_argument("-o", "--octave", type=int, help="Octave adjustment for whole file",
                    dest="octave_adjust", default=0)
parser.add_argument("-w", "--wav", type=str,
                    help="Output WAV file with simulated result.\n"
                         "To specify sample width append a ':n' parameter (default is 8-bit)",
                    dest="wav_file", default=None)


def bpm_to_tone_us(bpm: float) -> float:
    """Convert BPM tempo to tone period in microseconds."""
    return 6e7 / bpm


def tone_us_to_bpm(us: float) -> float:
    """Convert BPM tempo to tone period in microseconds."""
    return 6e7 / us


def format_midi_note(note: int) -> str:
    """Convert midi note 0-127 to note name."""
    return f"{NOTE_NAMES[note % 12]}{note // 12 - 1}"


def write_c_header(file: TextIO, data: bytes, arr_name: str):
    """Write C header file containing data array with a name."""
    file.write('#include "music.h"\n\n')
    file.write(f"static _FLASH uint8_t {arr_name}[] = {{\n")
    for i, b in enumerate(data):
        if i % 12 == 0:
            file.write("    ")
        file.write(f"0x{b:02x},")
        if i % 12 == 11:
            file.write("\n")
        else:
            file.write(" ")
    file.write("\n};")


class OutputFormat(Enum):
    BINARY = 0
    HEX_HEADER = 1


@dataclass
class Config:
    input_file: str
    output_file: str
    logger: Logger
    strategy_name: str
    tempo: int
    tempo_overriden: bool
    octave_adjust: int
    merge_midi_tracks: bool
    output_format: OutputFormat
    output_header_name: Optional[str]
    output_wav_file: Optional[str]
    output_wav_width: int


def create_config(args: argparse.Namespace) -> Config:
    """Validate input arguments and create typed configuration object."""
    input_path = Path(args.input_file)
    if not input_path.is_file():
        raise

    # logging
    log_level = next((e for e in LogLevel if e.name.lower() == args.log_level))
    log_file = sys.stderr if args.output_file == "-" else sys.stdout
    logger = Logger(log_file, log_level)

    # tempo
    tempo = args.tempo
    tempo_overriden = args.tempo is not None
    tempo_min = math.ceil(bpm_to_tone_us(BuzzerMusic.TEMPO_MIN))
    tempo_max = math.floor(bpm_to_tone_us(BuzzerMusic.TEMPO_MAX))
    if tempo_overriden and not (tempo_min <= tempo <= tempo_max):
        raise ValueError(f"Tempo override out of bounds (between {tempo_min} and {tempo_max} BPM)")

    output_format = OutputFormat.HEX_HEADER if args.header_name else OutputFormat.BINARY

    # WAV file specification
    wav_file = args.wav_file
    wav_width = 8
    if wav_file:
        parts = wav_file.split(":")
        if len(parts) == 2:
            wav_file = parts[0]
            try:
                wav_width = int(parts[1])
            except ValueError:
                raise ValueError("invalid WAV file sample width")
        elif len(parts) != 1:
            raise ValueError("invalid WAV file sample width specification")

    return Config(args.input_file, args.output_file, logger, args.track_strategy, tempo,
                  tempo_overriden, args.octave_adjust, args.merge_midi_tracks, output_format,
                  args.header_name, wav_file, wav_width)


class MidiConverter:
    """Class used to interpret configuration and output data and WAV file for buzzer music."""
    config: Config
    logger: Logger

    def __init__(self, config: Config):
        self.config = config
        self.logger = config.logger

    def convert(self) -> None:
        config = self.config
        midi = MidiFile(config.input_file, clip=True)

        track_count = len(midi.tracks)
        event_map = self._build_event_map(midi)
        self.logger.info(f"event map built, {len(event_map)} events in {track_count} tracks")

        # get tempo info
        tempo_map = self._get_tempo_map(event_map)
        tempo = self._get_overall_tempo(event_map, tempo_map)

        # create note frames for entire duration
        midi_duration = max(event_map.keys())
        frames = self._get_all_frames(tempo_map, tempo, midi_duration, midi.ticks_per_beat)
        self.logger.info(f"frames time computed, got {len(frames)} frames")

        # get notes played in each frame, for each MIDI track
        frames_notes = self._get_frame_notes(event_map, frames, track_count)

        # do some validation before applying track assignment strategy
        max_notes_at_once = self._count_max_notes_at_once(frames_notes)
        if max_notes_at_once > BuzzerTrack.MAX_TRACKS:
            self._abort(f"can't convert, up to {max_notes_at_once} notes played at once")
        else:
            self.logger.info(f"file has at most {max_notes_at_once} notes played at once")
        self._verify_note_range(frames_notes, tempo)

        # create buzzer music from frames notes
        # buzzer music will use average tempo since multiple tempos aren't supported
        self.logger.info(f"using '{config.strategy_name}' strategy")
        buzzer_music = self._create_buzzer_music(tempo, frames_notes)
        track_nums = (str(t.number) for t in buzzer_music.tracks)
        self.logger.info(f"buzzer music uses tracks {', '.join(track_nums)}")

        # write output data
        out_size = self._write_output_file(buzzer_music)
        self.logger.info(f"total data size is {out_size} bytes")

        # write output WAV
        self._create_wav_file(buzzer_music)

        self.logger.info("done")

    def _abort(self, message: Optional[str] = None) -> NoReturn:
        if message:
            self.logger.error(message)
        raise RuntimeError

    def _build_event_map(self, midi: MidiFile) -> MidiEventMap:
        """Group midi messages in all the tracks by the time at which they occur
        keep track of the original track number."""
        event_map: MidiEventMap = {}
        for i, track in enumerate(midi.tracks):
            time = 0
            for event in track:
                if round_delta_time:
                    time += round(event.time / 16) * 16
                else:
                    time += event.time
                if time not in event_map:
                    event_map[time] = []
                event_map[time].append((i, event))
        return event_map

    def _get_overall_tempo(self, event_map: MidiEventMap, tempo_map: MidiTempoMap) -> float:
        """Get overall tempo for buzzer music in us/tone."""
        if self.config.tempo_overriden:
            tempo = self.config.tempo
            self.logger.info(f"tempo map built, using tempo override of "
                             f"{tone_us_to_bpm(tempo):.0f} BPM")
        else:
            # get map of tempos in MIDI by time (MIDI clock)
            midi_duration = max(event_map.keys())
            tempo = self._get_average_tempo(tempo_map, midi_duration)
            if len(tempo_map) > 2:
                self.logger.warn("file has variable tempo, average tempo will be used.")
            self.logger.info(f"tempo map built, average tempo is {tone_us_to_bpm(tempo):.0f} BPM")
        return tempo

    def _get_tempo_map(self, event_map: MidiEventMap) -> MidiTempoMap:
        """Build MIDI tempo map (tempo in us/tone by MIDI time)."""
        tempo_map: MidiTempoMap = {0: 500000}
        for time, events in event_map.items():
            tempo_event = next((e[1] for e in events if e[1].type == "set_tempo"), None)
            if tempo_event:
                tempo_map[time] = tempo_event.tempo
        return tempo_map

    def _get_average_tempo(self, tempo_map: MidiTempoMap, midi_duration: int) -> float:
        """Get weighted average of tempo in map, by tempo duration."""
        avg_tempo = 0
        curr_tempo = 0
        last_tempo_time = 0
        for time, tempo in sorted(tempo_map.items()):
            avg_tempo += curr_tempo * (time - last_tempo_time)
            curr_tempo = tempo
            last_tempo_time = time
        avg_tempo += curr_tempo * (midi_duration - last_tempo_time)
        avg_tempo /= midi_duration
        return avg_tempo

    def _get_all_frames(self, tempo_map: MidiTempoMap, tempo: float, midi_duration: int,
                        ticks_per_beat: int) -> List[int]:
        """From average tempo, event map and tempo map, compute the MIDI clock for each 1/32nd
        of beat, for the duration of the whole file, while accounting for variable tempo."""
        frames: List[int] = []
        midi_ticks = 0.0
        tempo_map_sorted = sorted(tempo_map.items())
        curr_tempo = None
        while midi_ticks < midi_duration:
            if not curr_tempo or tempo_map_sorted and midi_ticks >= tempo_map_sorted[0][0]:
                curr_tempo = tempo_map_sorted[0][1]
                del tempo_map_sorted[0]
            frames.append(round(midi_ticks))
            # advance time to go to next timeframe, using average tempo as reference tempo
            # and taking clocks per tick into account
            midi_ticks += (curr_tempo / tempo) * ticks_per_beat / BuzzerNote.TIMEFRAME_RESOLUTION
        return frames

    def _get_frame_notes(self, event_map: MidiEventMap, frames: List[int],
                         track_count: int) -> FramesNotes:
        """Get all notes being played on each frame and in between frames, for each MIDI track.
        detect when notes go on and off during same frame to prevent omitting notes."""
        timelines: FramesNotes = [[] for _ in range(track_count)]
        notes_on: List[List[int]] = [[] for _ in range(track_count)]
        new_notes_on = set()
        for i, frame in enumerate(frames):
            events = list(event_map.get(frame, []))
            if i != len(frames) - 1:
                # also get all events in between this frame and the next,
                # in order to not miss any events
                for j in range(frame + 1, frames[i + 1]):
                    events += event_map.get(j, [])

            # update list of notes on per track
            for track_num, event in events:
                notes_on_track = notes_on[track_num]
                new_notes_on.clear()
                if event.type == "note_on" or event.type == "note_off":
                    note = event.note + self.config.octave_adjust * 12
                    if event.type == "note_on" and note not in notes_on_track:
                        # start playing note
                        # if note_on event and note is already being played, interpret as note_off (?).
                        notes_on_track.append(note)
                        new_notes_on.add(note)
                    else:
                        if note in new_notes_on:
                            # note went on during this frame, and off again! that means note is
                            # shorter than 1/32nd of a quarter note in overall tempo.
                            # lengthen note to last the whole frame instead of not registering it
                            self.logger.warn(f"note {note} at frame {frame} goes on and off "
                                             f"during same frame. Increasing note duration "
                                             f"(consider overriding tempo).")
                        else:
                            if note not in notes_on_track:
                                self.logger.info(f"note {event.note} already off "
                                                 f"at MIDI time {frame}")
                            else:
                                notes_on_track.remove(note)

            # save notes for frame
            for j, timeline in enumerate(timelines):
                timeline.append(list(notes_on[j]))

        return timelines

    def _count_max_notes_at_once(self, frames_notes: FramesNotes) -> int:
        """Count maximum number of notes played at once."""
        return max(len(notes) for track_notes in frames_notes for notes in track_notes)

    def _verify_note_range(self, frames_notes: FramesNotes, tempo: float) -> None:
        """Check that no note in file exceeds the largest timer range and
        give some information on notes and timing if bad notes found."""
        bad_notes = 0
        last_bad_note = -1
        for track_notes in frames_notes:
            for i, frame_notes in enumerate(track_notes):
                for j, note in enumerate(frame_notes):
                    track_found = False
                    for track_range in BuzzerTrack.TRACK_RANGES:
                        if BuzzerNote.from_midi(note) in track_range:
                            track_found = True
                            break
                    if not track_found and note != last_bad_note:
                        # bad note, give some info on it
                        # given time is approximate since based on overall tempo.
                        time = i / (BuzzerNote.TIMEFRAME_RESOLUTION * 1e6) * tempo
                        self.logger.error(f"can't convert, found note {format_midi_note(note)} "
                                          f"exceeding timer range (at around {time:.1f} s)")
                        bad_notes += 1
                        last_bad_note = note
                        if bad_notes >= 8:
                            self._abort("(yet more notes exceeding range found)")
        if bad_notes > 0:
            self._abort()

    def _get_encoded_tempo(self, tempo: float) -> int:
        """Encode tempo from us/tone to byte used by buzzer music format."""
        if tempo < BuzzerMusic.TEMPO_MAX:
            self.logger.warn(f"tempo value is too high to be encoded ({tone_us_to_bpm(tempo)}), "
                             f"consider overriding it")
            return 0
        elif tempo > BuzzerMusic.TEMPO_MIN:
            self.logger.warn(f"tempo value is too low to be encoded ({bpm_to_tone_us(tempo)}), "
                             f"consider overriding it")
            return 255
        else:
            return BuzzerMusic.encode_tone_us_tempo(tempo)

    def _create_buzzer_music(self, tempo: float, frames_notes: FramesNotes) -> BuzzerMusic:
        """Create buzzer music from frames notes using specified strategy."""
        # create empty buzzer music with set tempo
        encoded_tempo = self._get_encoded_tempo(tempo)
        music = BuzzerMusic(encoded_tempo)

        # use specified strategy to create buzzer tracks from frames notes
        track_strategy = TRACK_STRATEGIES[self.config.strategy_name]
        track_strategy.merge_midi_tracks = self.config.merge_midi_tracks
        try:
            tracks = track_strategy.create_tracks(self.logger, frames_notes)
        except TrackStrategyFailError:
            # strategy failed, abort
            self._abort(f"failed to apply '{self.config.strategy_name}' strategy.")

        music.tracks = tracks
        return music

    def _write_output_file(self, music: BuzzerMusic) -> int:
        """Output data file from buzzer music."""
        config = self.config

        # encode buzzer music
        try:
            data = music.encode()
        except RuntimeError as e:
            self._abort(str(e))

        # write data to file / stdout
        try:
            mode = "w" if config.output_format == OutputFormat.HEX_HEADER else "wb"
            if config.output_file == '-':
                fd = os.fdopen(sys.stdout.fileno(), mode)
            else:
                fd = open(config.output_file, mode)

            # output to file
            if config.output_format == OutputFormat.HEX_HEADER:
                write_c_header(fd, data, config.output_header_name)
            else:
                fd.write(data)

            fd.flush()
            if config.output_file != "-":
                fd.close()
                self.logger.info(f"buzzer music data output to {config.output_file}")
            else:
                self.logger.info("buzzer music data output to stdout")
        except IOError as e:
            self._abort(f"could not write output file: {e}")

        return len(data)

    def _create_wav_file(self, music: BuzzerMusic) -> None:
        """Output WAV file from buzzer music."""
        config = self.config
        if config.output_wav_file:
            try:
                create_wav_file(music, config.output_wav_file, config.output_wav_width,
                                config.output_file != "-" and config.logger.level == LogLevel.INFO)
                self.logger.info(f"WAV file output to {config.output_wav_file} "
                                 f"({config.output_wav_width}-bit samples)")
            except RuntimeError as e:
                self._abort(f"failed to create WAV file: {e}")


def main() -> None:
    args = parser.parse_args()
    try:
        config = create_config(args)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    converter = MidiConverter(config)
    try:
        converter.convert()
    except RuntimeError:
        sys.exit(1)


if __name__ == '__main__':
    main()
