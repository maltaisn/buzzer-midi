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
#include <util/delay.h>

#if defined(__AVR_ATmega328P__)
#define MAX_TRACKS 6
#elif defined(__AVR_ATmega3208__)
#define MAX_TRACKS 3
#endif

#define TRACK_END 0xfe
#define NO_NOTE 0xff

#ifdef __CLION_IDE_
#define __flash
#endif
#define _FLASH const __flash

extern _FLASH uint16_t TIMER_NOTES[];

typedef struct {
    // current track pos in music data array
    // null if track isn't used or when track has ended.
    _FLASH uint8_t* track_pos;

    // note being currently played.
    // the note correspond to an index in TIMERx_NOTES arrays.
    uint8_t note;

    // time left for note currently being played, in 1/32th of a tone, -1.
    uint16_t note_duration;
} track_t;

typedef struct {
    // music data:
    // 0x00: tempo, calculated roughly as 1 tone = 8200 * (tempo) us.
    // 0x01+: track data (at least one track)
    //
    // track data:
    // 0x00: track number, 0-5 (0-1: timer0, 2-3: timer1, 4-5: timer2).
    // 0x01-0x02: track length, in bytes, including header (little endian).
    // 0x03+: note data.
    // last byte: 0xfe
    //
    // note data: each note consists of two bytes:
    // 0x00: note, where 0 is C2 and 71 is B7. 0xff is used to play nothing.
    // 0x01-0x02: note duration, in 1/32th of a tone, minus one.
    //   duration can be encoded on one byte (<128) or two bytes.
    //   if first byte doesn't have MSB set, then it's only one byte. two bytes encoding is little-endian.
    //   for example: 7f = 0x7f, 80 01 = 0x80, 80 10 = 0x800, ff ff = 0x7fff
    _FLASH uint8_t* music_data;

    // music tracks
    // - track 0-1: timer0, C4 to B7, pin 6 and 5
    // - track 2-3: timer1, C2 to B7, pin 9 and 10
    // - track 4-5: timer2, C4 to B7, pin 11 and 3
    track_t tracks[MAX_TRACKS];

    // music tempo (1 tone = 8200 * (tempo) us)
    uint8_t tempo;
} music_t;

/**
 * initialize music state from music data.
 * can be used to reinitialize music for looping.
 */
void music_init(_FLASH uint8_t* music_data, music_t* state);

/**
 * must be called periodically to update notes currently being played.
 * @param adjust negative adjustment for tempo, a value of 1 removes 256 us from the delay.
 * @return true when music is playing, false when done.
 */
bool music_loop(music_t *state, uint16_t adjust);

#endif //MUSIC_H
