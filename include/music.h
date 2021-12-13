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
#define TRACK_END 0xfe
#define NO_NOTE 0xff

typedef struct {
    // Current track pos in music data array
    // TRACK_POS_END if track isn't used or when track has ended.
    _FLASH uint8_t* track_pos;

    // Note being currently played (0-72).
    uint8_t note;

    // Time left for note currently being played, in 1/32nd of a beat, -1.
    uint16_t note_duration;
} track_t;

typedef struct {
    // Music data:
    // 0x00: tempo encoded as the number of 256 us slices in 1/32nd of a beat,
    //       Can also be calculated as follows:
    //       --> tempo = (7324 / [BPM] - 1)
    //       --> tempo = ([us per beat] / 8192 - 1)
    //       higher values result in slower tempo, lower values in faster tempo.
    //       tempo = 0 is 7324 BPM and tempo = 255 is 29 BPM.
    //
    // 0x01+: track data (at least one track)
    //
    // Track data:
    // 0x00: track number, 0-(MAX_TRACKS-1)
    // 0x01-0x02: track length, in bytes, including header (little endian).
    // 0x03+: note data.
    // last byte: 0xfe
    //
    // Note data: each note consists of 2 or 3 bytes:
    // 0x00: note, where 0 is C2 and 72 is C8 (73 playable notes). 0xff is used to play nothing.
    // 0x01-0x02: note duration, in 1/32nd of a beat, minus one.
    //   duration can be encoded on one byte (<128) or two bytes.
    //   if first byte doesn't have MSB set, then it's only one byte. two bytes encoding is little-endian.
    //   for example: 7f = 0x7f, 80 01 = 0x80, 80 10 = 0x800, ff ff = 0x7fff
    _FLASH uint8_t* music_data;

    // music tracks
    // - track 0-1: timer0, C4 to B7, pin 6 and 5
    // - track 2-3: timer1, C2 to B7, pin 9 and 10
    // - track 4-5: timer2, C4 to B7, pin 11 and 3
    track_t tracks[MAX_TRACKS];

    // music tempo (1 beat = 8200 * (tempo) us)
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
