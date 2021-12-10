
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

#if !defined(__AVR_ATmega328P__) && !defined(__AVR_ATmega3208__)
#error "Unsupported target"
#endif

void impl_setup(void);

void impl_reset(void);

void impl_play_note(const track_t *track, uint8_t track_num);

#endif //IMPL_H
