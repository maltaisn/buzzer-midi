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

import math
import random
from abc import ABC
from typing import List, Optional, Tuple

from logger import Logger
from music_data import BuzzerMusic, BuzzerTrack, BuzzerNote, FramesNotes, ChannelSpec


class TrackStrategyFailError(Exception):
    """Exception thrown when a track strategy fails for a set of frames notes."""
    pass


class TrackStrategy(ABC):
    """Base strategy for assigning notes to each track (timer) from frames notes."""
    merge_midi_tracks: bool

    def __init__(self):
        self.merge_midi_tracks = False

    def create_tracks(self, logger: Logger, channels_spec: List[ChannelSpec],
                      frames_notes: FramesNotes) -> List[BuzzerTrack]:
        """
        Create a list of buzzer tracks by placing the notes in each frame.
        Subclasses must not modify frames_notes!
        :raises TrackStrategyFailError if strategy failed to be applied
        """
        tracks = [BuzzerTrack(i, spec) for i, spec in enumerate(channels_spec)]
        # which MIDI track a buzzer track has been set to, or None if none yet.
        midi_track_assignment: List[Optional[int]] = [None] * len(channels_spec)

        def filter_tracks(track: BuzzerTrack):
            midi_asg = midi_track_assignment[track.channel]
            return (bnote in track.spec.note_range and
                    (self.merge_midi_tracks or midi_asg is None or midi_track == midi_asg))

        for i in range(len(frames_notes[0])):
            # unassigned tracks for current frame
            unassigned_tracks = {track.channel: track for track in tracks}

            for midi_track, midi_track_notes in enumerate(frames_notes):
                for note in midi_track_notes[i]:
                    bnote = BuzzerNote.from_midi(note)

                    # filter available tracks to keep only tracks which have had no note
                    # assigned yet to them or tracks which have had notes from this MIDI track.
                    # also keep only tracks on which note can be played
                    legal_tracks = list(filter(filter_tracks, unassigned_tracks.values()))
                    if not legal_tracks:
                        raise TrackStrategyFailError

                    # apply strategy to choose track for note
                    track_num = self.assign_track(legal_tracks, bnote)
                    if track_num is None:
                        # failed to assign note to a track, so strategy failed
                        raise TrackStrategyFailError

                    del unassigned_tracks[track_num]
                    if midi_track_assignment[track_num] is None:
                        # first note assigned to this track, remember which MIDI track
                        midi_track_assignment[track_num] = midi_track

                    tracks[track_num].add_note(bnote)

            # add "none" notes for remaining unassigned tracks
            for track in unassigned_tracks.values():
                track.add_note(BuzzerNote.NONE)

        for track in tracks:
            track.finalize()

        # discard tracks with only a single "none" note
        return list(filter(lambda t: len(t.notes) > 0, tracks))

    def assign_track(self, tracks: List[BuzzerTrack], bnote: int) -> int:
        """
        Assign a note to one of the available tracks and return the track number.
        The tracks list can be modified safely.
        :raises TrackStrategyFailError if strategy failed to be applied
        """
        pass


class ClosestTrackStrategy(TrackStrategy):
    """
    assign note to the track that is playing or last played the closest note.
    thus, separate hands should be played separatedly no matter the order in MIDI.
    a track currently playing no note is considered the farthest.
    if two tracks are considered equal using this method, use the track with the most notes,
    then the track with the lowest track number.
    """

    def assign_track(self, tracks: List[BuzzerTrack], bnote: int) -> Optional[int]:
        if len(tracks[0].notes) == 0:
            # no notes assigned yet, fallback on first fit.
            return tracks[0].channel

        # find track playing note closest to this note
        closest_track: Optional[int] = None
        closest_count = 0
        min_note_dist = 0
        for i, track in enumerate(tracks):
            curr_note = track.notes[-1].note
            if curr_note == BuzzerNote.NONE and len(track.notes) > 1:
                curr_note = track.notes[-2].note
            note_dist = math.inf if curr_note == BuzzerNote.NONE else abs(bnote - curr_note)
            if closest_track is None or note_dist < min_note_dist or \
                    (note_dist == min_note_dist and len(track.notes) > closest_count):
                closest_track = track.channel
                closest_count = len(track.notes)
                min_note_dist = note_dist

        return closest_track


class ClosestAverageTrackStrategy(TrackStrategy):
    """
    assign note to the track that has an average note closest to note.
    if two tracks are considered equal using this method, use the track with the most notes,
    then the track with the lowest track number.
    """
    _tracks_sum: List[int]
    _tracks_count: List[int]

    def create_tracks(self, logger: Logger, channels_spec: List[ChannelSpec],
                      frames_notes: FramesNotes) -> List[BuzzerTrack]:
        self._tracks_sum = [0] * len(channels_spec)
        self._tracks_count = [0] * len(channels_spec)
        return super().create_tracks(logger, channels_spec, frames_notes)

    def assign_track(self, tracks: List[BuzzerTrack], bnote: int) -> Optional[int]:
        closest_track: Optional[int] = None
        if len(tracks[0].notes) == 0:
            # no notes assigned yet, fallback on first fit.
            closest_track = tracks[0].channel
        else:
            # find track playing average note closest to this note
            min_note_dist = 0
            for i, track in enumerate(tracks):
                note_count = self._tracks_count[i]
                note_dist = math.inf if note_count == 0 else \
                    abs(bnote - self._tracks_sum[i] / note_count)
                if closest_track is None or note_dist < min_note_dist:
                    closest_track = track.channel
                    min_note_dist = note_dist

        if closest_track is not None:
            self._tracks_sum[closest_track] += bnote
            self._tracks_count[closest_track] += 1
        return closest_track


class FirstFitTrackStrategy(TrackStrategy):
    """
    assign note to first track with a timer than can play it.
    If using preferred, prefer buzzer with smaller range if note fits
    """
    use_preferred: bool

    def __init__(self, use_preferred: bool):
        super().__init__()
        self.use_preferred = use_preferred

    def assign_track(self, tracks: List[BuzzerTrack], bnote: int) -> Optional[int]:
        if self.use_preferred:
            tracks.sort(key=lambda t: len(t.spec.note_range))
        return tracks[0].channel


class RandomTrackStrategy(TrackStrategy):
    """
    assign note to random track, but prioritize timers with shorter range
    if note fits, otherwise strategy will nearly always fail.
    this strategy is somewhat useless, although it does have the interesting side effect
    of keeping the music recognizable even when only 1 out of 6 buzzers is connected.
    """

    def assign_track(self, tracks: List[BuzzerTrack], bnote: int) -> Optional[int]:
        tracks.sort(key=lambda t: len(t.spec.note_range))
        smallest_range = tracks[0].spec.note_range
        tracks = [t for t in tracks if t.spec.note_range == smallest_range]
        return random.choice(tracks).channel


class AutoTrackStrategy(TrackStrategy):
    """
    default strategy of trying strategies in order
    """

    def create_tracks(self, logger: Logger, channels_spec: List[ChannelSpec],
                      frames_notes: FramesNotes) -> List[BuzzerTrack]:
        # try strategies in order
        for s in auto_strategies:
            name, strategy = s
            strategy.merge_midi_tracks = self.merge_midi_tracks
            try:
                tracks = strategy.create_tracks(logger, channels_spec, frames_notes)
            except TrackStrategyFailError:
                logger.info(f"'{name}' strategy couldn't be applied")
            else:
                logger.info(f"'{name}' strategy successfully applied")
                return tracks
        raise TrackStrategyFailError


class OptimizeSizeTrackStrategy(TrackStrategy):
    """
    try all strategies and use the one that gives the smallest data size.
    """

    def create_tracks(self, logger: Logger, channels_spec: List[ChannelSpec],
                      frames_notes: FramesNotes) -> List[BuzzerTrack]:
        best_tracks: Optional[List[BuzzerTrack]] = None
        best_track_strategy: Optional[str] = None
        best_size: int = 0
        music = BuzzerMusic(0)
        for s in normal_strategies:
            name, strategy = s
            strategy.merge_midi_tracks = self.merge_midi_tracks
            try:
                tracks = strategy.create_tracks(logger, channels_spec, frames_notes)
            except TrackStrategyFailError:
                logger.info(f"'{name}' strategy couldn't be applied")
            else:
                music.tracks = tracks
                size = len(music.encode())
                if not best_tracks or size < best_size:
                    best_tracks = tracks
                    best_track_strategy = name
                    best_size = size
                logger.info(f"'{name}' strategy produced data size of {size} bytes")

        if not best_tracks:
            raise TrackStrategyFailError()
        logger.info(f"'{best_track_strategy}' strategy selected")
        return best_tracks


class OptimizeChannelsTrackStrategy(TrackStrategy):
    """
    try all strategies and use the one that gives the smallest number of channels used.
    if same number of channels, compare size
    """

    def create_tracks(self, logger: Logger, channels_spec: List[ChannelSpec],
                      frames_notes: FramesNotes) -> Optional[List[BuzzerTrack]]:
        best_tracks: Optional[List[BuzzerTrack]] = None
        best_track_strategy: Optional[str] = None
        best_size: int = 0
        music = BuzzerMusic(0)
        for s in normal_strategies:
            name, strategy = s
            strategy.merge_midi_tracks = self.merge_midi_tracks
            try:
                tracks = strategy.create_tracks(logger, channels_spec, frames_notes)
            except TrackStrategyFailError:
                logger.info(f"'{name}' strategy couldn't be applied")
            else:
                music.tracks = tracks
                size = len(music.encode())
                if not best_tracks or len(tracks) < len(best_tracks) or \
                        len(tracks) == len(best_tracks) and size < best_size:
                    best_tracks = tracks
                    best_track_strategy = name
                    best_size = size
                logger.info(f"'{name}' strategy used {len(tracks)} channels ({size} bytes)")
        if not best_tracks:
            raise TrackStrategyFailError
        logger.info(f"'{best_track_strategy}' strategy selected")
        return best_tracks


auto_strategies: List[Tuple[str, TrackStrategy]] = [
    ("closest", ClosestTrackStrategy()),
    ("closest_avg", ClosestAverageTrackStrategy()),
    ("first_fit_pref", FirstFitTrackStrategy(True)),
    ("random", RandomTrackStrategy()),
]

normal_strategies: List[Tuple[str, TrackStrategy]] = [
    ("closest", ClosestTrackStrategy()),
    ("closest_avg", ClosestAverageTrackStrategy()),
    ("first_fit", FirstFitTrackStrategy(False)),
    ("first_fit_pref", FirstFitTrackStrategy(True)),
]
