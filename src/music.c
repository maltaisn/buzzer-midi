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

#define IMMEDIATE_PAUSE_OFFSET 0x55
#define SHORT_PAUSE_OFFSET 0xaa
#define IMMEDIATE_PAUSE_MASK 0x8000

#define TRACK_END 0xff

/**
 * Read the next note in track data and set it as current note with its duration.
 * Preconditions: track->duration_left == 0 && track->notes_data != TRACK_POS_END.
 */
static inline void track_seek_note(track_t *track) {
    if (track->duration_total & IMMEDIATE_PAUSE_MASK) {
        // note is followed by an immediate pause.
        track->note = NO_NOTE;
        track->duration_left = track->immediate_pause;
        track->duration_total &= ~IMMEDIATE_PAUSE_MASK;
        return;
    }

    uint8_t note = *track->note_data++;
    if (note == TRACK_END) {
        // no more notes in track
        track->note_data = TRACK_POS_END;
        return;
    }

    if (note >= SHORT_PAUSE_OFFSET) {
        // single byte encoding for pause, no associated duration.
        // note that this doesn't update duration_total!
        track->duration_left = note - SHORT_PAUSE_OFFSET;
        track->note = NO_NOTE;
        return;
    }

    uint8_t duration = track->duration_data[0];
    if (track->duration_repeat) {
        // last duration continues to be repeated.
        --track->duration_repeat;
    } else if (duration & 0x80) {
        if (duration & 0x40) {
            // two bytes duration encoding.
            track->duration_total = (duration & 0x3f) << 8 | track->duration_data[1];
            track->duration_data += 2;
        } else {
            // last duration will be repeated a number of times.
            track->duration_repeat = duration - 0x80;
            ++track->duration_data;
        }
    } else {
        // single byte duration encoding.
        track->duration_total = duration;
        ++track->duration_data;
    }
    track->duration_left = track->duration_total;
    if (note >= IMMEDIATE_PAUSE_OFFSET) {
        note -= IMMEDIATE_PAUSE_OFFSET;
        track->duration_total |= IMMEDIATE_PAUSE_MASK;
    }
    track->note = note;
}

void music_init(_FLASH uint8_t* music_data, music_t* state) {
    state->music_data = music_data;
    state->tempo = *music_data++;
    _FLASH uint8_t* track_pos = music_data;
    for (int i = 0; i < MAX_CHANNELS; ++i) {
        track_t *track = &state->tracks[i];
        if (track_pos[0] != i) {
            // track doesn't exist
            track->note_data = TRACK_POS_END;
            continue;
        }
        uint16_t track_length = track_pos[1] | track_pos[2] << 8;
        uint16_t duration_offset = track_pos[3] | track_pos[4] << 8;
        track->note_data = track_pos + 6;
        track->duration_data = track_pos + duration_offset;
        track->immediate_pause = track_pos[5];
        track->duration_left = 0;
        track->duration_total = 0;
        track->duration_repeat = 0;
        track_pos += track_length;
    }
}

bool music_loop(music_t *state) {
    bool track_playing = false;
    for (int channel = 0; channel < MAX_CHANNELS; ++channel) {
        track_t *track = &state->tracks[channel];
        if (track->note_data != TRACK_POS_END) {
            if (track->duration_left == 0) {
                // note ended, go to next note
                track_seek_note(track);
                impl_play_note(track, channel);
            } else {
                --track->duration_left;
            }
            track_playing = true;
        }
    }
    return track_playing;
}
