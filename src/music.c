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
#include <impl.h>
#include <stdbool.h>

/**
 * Read the next note in track data and set it as current note.
 */
static inline void track_seek_note(track_t *track) {
    if (track->track_pos != TRACK_POS_END) {
        track->note = track->track_pos[0];
        if (track->note == TRACK_END) {
            // track ended, stop note.
            track->note = NO_NOTE;
            track->note_duration = 0;
            track->track_pos = TRACK_POS_END;
        } else {
            track->note_duration = track->track_pos[1];
            if (track->note_duration & 0x80) {
                // two bytes duration encoding
                track->note_duration = track->track_pos[2] << 7 | (track->note_duration & 0x7f);
                track->track_pos += 3;
            } else {
                // one byte duration encoding
                track->track_pos += 2;
            }
        }
    }
}

void music_init(_FLASH uint8_t* music_data, music_t* state) {
    state->music_data = music_data;
    state->tempo = *music_data++;
    _FLASH uint8_t* track_pos = music_data;
    for (int i = 0; i < MAX_TRACKS; ++i) {
        track_t *track = &state->tracks[i];
        if (track_pos[0] != i) {
            // track doesn't exist
            track->track_pos = TRACK_POS_END;
            continue;
        }
        track->track_pos = track_pos + 3;
        track->note_duration = 0;
        track_pos += track_pos[1] | track_pos[2] << 8;
    }
}

bool music_loop(music_t *state) {
    bool track_playing = false;
    for (int i = 0; i < MAX_TRACKS; ++i) {
        track_t *track = &state->tracks[i];
        if (track->track_pos != TRACK_POS_END) {
            if (track->note_duration == 0) {
                // note ended, go to next note
                track_seek_note(track);
                impl_play_note(track, i);
            } else {
                --track->note_duration;
            }
            track_playing = true;
        }
    }
    return track_playing;
}
