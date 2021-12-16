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

#ifndef DEFS_H
#define DEFS_H

#if defined(TARGET_ATMEGA328P)
#define MAX_CHANNELS 2
#elif defined(TARGET_ATMEGA328P_SPLIT)
#define MAX_CHANNELS 6
#elif defined(TARGET_ATMEGA3208)
#define MAX_CHANNELS 3
#else
#error "Unsupported target"
#endif

#if defined(__AVR_ATmega328P__) && !defined(__CLION_IDE_)
#define _FLASH const __flash
#else
// on ATmega3208, flash is memory mapped and all const are put in flash automatically.
// using __flash is counterproductive since it results in 3 cycles LPM vs 2 cycles LD...
#define _FLASH const
#endif

#endif //DEFS_H
