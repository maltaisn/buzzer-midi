/*
 * Copyright 2021 Nicolas Maltais
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#ifndef MUSIC_H
#define MUSIC_H

#include <stdint.h>
#include <stdbool.h>
#include <defs.h>

#define TRACK_POS_END ((_FLASH uint8_t*) 0)

#define NO_NOTE 0x54

typedef struct {
    // Current position in note data array.
    // TRACK_POS_END if channel isn't used or when track has ended.
    _FLASH uint8_t* note_data;
    // Current position in duration data array.
    // Undefined if channel isn't used or when track has ended.
    _FLASH uint8_t* duration_data;
    // Pause duration used after note using immediate pause encoding.
    uint8_t immediate_pause;
    // Note being currently played (0-83).
    uint8_t note;
    // Time left for note currently being played, in 1/16th of a beat, -1.
    uint16_t duration_left;
    // Total duration of note currently being played, in 1/16th of a beat, -1.
    // The MSB of this field indicates whether the current note is followed by the most common pause.
    uint16_t duration_total;
    // Number of times that the current note duration is to be repeated yet.
    uint8_t duration_repeat;
} track_t;

typedef struct {
    // Music data:
    // - 0x00:
    //       Tempo encoded as the number of 256 us slices in 1/16th of a beat, minus one.
    //       Can also be calculated as follows:
    //       --> tempo = (14648.4 / [BPM] - 1)
    //       --> tempo = ([us per beat] / 4096  - 1)
    //       Higher values result in slower tempo, lower values in faster tempo.
    //       tempo = 0 is 14648 BPM and tempo = 255 is 57 BPM.
    //       There's at most 1% error in the 60-300 BPM range.
    // - 0x01-end:
    //       Track data. Tracks with no data can be omitted.
    // - end: last byte is 0xff
    //
    // Track data:
    // - 0x00:
    //       Channel number, 0 to (MAX_CHANNELS-1).
    //       Must be greater than the channel number of previous tracks in music data.
    // - 0x01-0x02:
    //       Track length, in bytes, including header (little endian).
    // - 0x03-0x04: (<duration_offset>)
    //       Duration array offset from first byte of track (little endian).
    // - 0x05:
    //       Immediate pause duration in 1/16th of a beat.
    // - 0x06-<duration_offset-1>:
    //       Array of notes
    //       - 0x00-0x53: notes from C2 to B8 (*)
    //       - 0x54:      pause (*)
    //       - 0x55-0xa8: notes from C2 to B8, followed by the immediate pause (*)
    //       - 0xa9:      pause, followed by the immediate pause (*)
    //       - 0xaa-0xfe: pause of duration (byte - 0xaa)
    //       - 0xff:      last byte of note array
    //       (*): note byte has an associated duration in duration array.
    // - <duration_offset>-end:
    //       Array of note durations
    //       - 0x00-0x7f: single byte duration, minus one. (1-128)
    //       - 0x80-0xbf: indicates that the current note and the (byte - 0x80) following
    //                    notes have the same duration as the previously decoded duration.
    //                    Note that single byte pauses are not counted as a previous duration.
    //       - 0xc0-0xff: two bytes duration, minus one. (1-16384)
    //                    duration = ((byte0 & 0x3f) << 8 | byte1)
    //
    // Example music data:
    //   0x79, 0x01, 0x07, 0x00, 0x07, 0x00, 0x00, 0xff, 0x03, 0x26, 0x00, 0x17,
    //   0x00, 0x04, 0x18, 0x19, 0x24, 0x25, 0x26, 0x27, 0x28, 0x29, 0x30, 0x31,
    //   0x6d, 0x6e, 0x54, 0xa9, 0xc0, 0x18, 0x18, 0xff, 0x3f, 0xc1, 0xf3, 0x07,
    //   0x83, 0x82, 0x0f, 0x80, 0xc0, 0x83, 0x7e, 0xff, 0xff, 0x00, 0xff,
    //
    // - 0x79: tempo, 120.07 BPM
    // - track 0 data:
    //     - 0x01: channel 1
    //     - 0x07 0x00: length of track is 7 bytes.
    //     - 0x07 0x00: duration data starts 7 bytes after start of track data (meaning there's none)
    //     - 0x00: immediate pauses have a duration of 1.
    //     - 0xff: last byte of note data.
    // - track 1 data:
    //     - 0x03: channel 2
    //     - 0x27 0x00: length of track is 39 bytes.
    //     - 0x18 0x00: duration data starts 24 bytes after start of track data.
    //     - 0x04: immediate pauses have a duration of 5.
    //     - track data (described in <note data> / <duration data> format):
    //         - 0x18 / 0x3f: C4, duration 64.
    //         - 0x19 / 0xc1 0xf3: C#4, duration 500.
    //         - 0x24 / 0x08: C5, duration 8.
    //         - 0x25 0x26 0x27 0x28 / 0x83: C#5, D5, D#5, E5, duration 8 (same as last duration).
    //         - 0x29 0x30 0x31 / 0x82: F5, F#5, G5, duration 8 (same as last duration).
    //         - 0x6d / 0x0f: C4 duration 16, followed by pause of duration 5 (immediate).
    //         - 0x6e / 0x80: C#4 duration 16 (same as last duration), followed by pause of duration 5 (immediate).
    //         - 0x54 / 0xc0 0x83: pause, duration 132 (3 bytes encoding).
    //         - 0xa9 / 0x7e: pause followed by immediate pause, for total duration of 132 (2 bytes encoding).
    //         - 0xc0 /: pause, duration 23.
    //         - 0x18 0x18 / 0xff 0xff 0x00: C4, duration 16385.
    //         - 0xff: last byte of note data.
    // - track 2 data: not present hence track is unused.
    // - 0xff: last byte of music data
    _FLASH uint8_t* music_data;

    // Music tracks, one per channel.
    // Maximum number of channels and playable notes for each channel depends on implementation.
    track_t tracks[MAX_CHANNELS];

    // Music tempo (see calculation above).
    uint8_t tempo;
} music_t;

/**
 * Initialize music state from music data.
 * Can be used to reinitialize music state for looping.
 */
void music_init(_FLASH uint8_t* music_data, music_t* state);

/**
 * Must be called periodically to update notes currently being played.
 * @return Returns true when music is playing, false when done.
 */
bool music_loop(music_t *state);

#endif //MUSIC_H
