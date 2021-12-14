
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

#ifndef IMPL_H
#define IMPL_H

#include <stdint.h>
#include <music.h>

/**
 * Setup registers for implementation.
 */
void impl_setup(void);

/**
 * Stop playing sound and reset implementation state.
 */
void impl_reset(void);

/**
 * Callback from main program to implementation to update the
 * note currently being played on a channel by a track.
 * If track->note is NO_NOTE, the implementation should stop playing the previous note.
 * Otherwise, the implementation should start (or continue) playing the current note.
 *
 * @param track The track in which a note changed.
 * @param channel The channel assigned to the track (1 - (MAX_CHANNELS-1)).
 */
void impl_play_note(const track_t *track, uint8_t channel);

#endif //IMPL_H
