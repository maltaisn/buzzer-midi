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

#include <music.h>
#include <music_data.h>
#include <impl.h>
#include <util/delay.h>

#ifndef LOOP
// Whether to loop the music data playback indefinitely.
#define LOOP true
#endif

// Adjustment by 256 us increments to account for time spent
// reading new note data after each 1/32nd of a beat.
// Alternatively, music_loop can be called from a timer interrupt
// with the appropriate period (256 us * music_state.tempo).
#define TEMPO_ADJUST -1

int main() {
    // setup registers for implementation
    impl_setup();

    // play music in a loop
    do {
        // initialize music state
        static music_t music_state;
        music_init(music_data, &music_state);
        impl_reset();

        // play all notes
        while (music_loop(&music_state)) {
            // wait for roughly 1/32nd of a beat, with adjustment
            uint8_t delay = music_state.tempo + TEMPO_ADJUST;
            while (delay > 0) {
                _delay_us(256);
                --delay;
            }
        }
    } while (LOOP);
}

