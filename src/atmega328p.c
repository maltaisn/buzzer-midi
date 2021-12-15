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

// ==== 2 channels on 1 buzzer implementation for ATmega328P ====
//
// Outputs notes from 2 channels to a single output connected to a buzzer.
// Volume control is possible by changing the range of the PWM duty cycle.
//
// Timer 2 is used to output a PWM signal with varying duty cycle.
// If more channels are "on" at a time, the duty cycle is higher and inversely.
// A channel is "on" for half of the period of the note it's playing.
// The current on/off state of a channel is kept in a variable.
// Timer 0 and Timer 1 are used to toggle that state and update the
// PWM duty cycle during their interrupt.
//
// Channel 0: uses Timer 0, C2 to C#7 playable
// Channel 1: uses Timer 1, C2 to C8 playable
// PWM frequency is 62.5 kHz.
//
// It would technically be possible to have up to four channels using the
// same timer multiplexing trick as in the ATmega328P split implementation.
//
// Resources used:
// - Timer0, Timer1, Timer2
// - About 120k cycles per second for the interrupts (0.4% usage at 16 MHz).
//   (counting 60 cycles per interrupt, x2, playing a 500 Hz note).

#ifdef TARGET_ATMEGA328P

#include <music.h>
#include <avr/io.h>
#include <avr/interrupt.h>

// different volume levels are supported by varying the PWM duty cycle range
// volume is not changeable at runtime in the current implementation but this isn't an issue.
#define VOLUME_LEVEL 2

// Whether to output a pair of differential signals to drive a H-bridge.
// PA3 is the normal output and PA2 is the inverted input.
// if disabled, only PA3 is output.
#define HBRIDGE_OUTPUT 1

// Timer counts for TCA PWM timer.
// The number corresponds to the number of bits set in the 0-7 position,
// multiplied by an arbitrary constant to account for the volume.
_FLASH uint8_t PWM_LEVELS[] = {
    0, 15, 15, 31,     // volume = 0, duty cycle 0.4 to 12.5%
    0, 31, 31, 63,     // volume = 1, duty cycle 0.4 to 25%
    0, 63, 63, 127,    // volume = 2, duty cycle 0.4 to 50%
    0, 127, 127, 255,  // volume = 3, duty cycle 0.4 to 100%
};

// These arrays contain timer counts to play each note.
// Timer counts are calculated using the following formula:
//   [count] = round([f_cpu] / [prescaler] / [note frequency] / 2) - 1
// See the utils/error_analysis.py script for more details.
// Maximum error for Timer 0 is 0.3 semitone (enough to sound very weird sometimes).
_FLASH uint8_t TIMER0_NOTES[] = {
    252, 238, 224, 212, 200, 189, 178, 168, 158, 149,
    141, 133, 126, 118, 112, 105, 99, 94, 88, 83,
    79, 74, 70, 66, 62, 59, 55, 52, 49, 46,
    44, 41, 39, 37, 35, 33, 31, 29, 27, 26,
    24, 23, 21, 20, 19, 18, 17, 16, 15, 14,
    13,
};
// Maximum error for Timer 1 is 0.01 semitone.
_FLASH uint16_t TIMER1_NOTES[] = {
    // Timer 1 notes start here
    15288, 14430, 13620, 12855, 12134, 11453, 10810, 10203, 9630, 9090,
    8580, 8098, 7644, 7214, 6809, 6427, 6066, 5726, 5404, 5101,
    4815, 4544, 4289, 4049, 3821, 3607, 3404, 3213, 3033, 2862,
    2702, 2550, 2407, 2272, 2144, 2024, 1910, 1803, 1702, 1606,
    1516, 1431, 1350, 1275, 1203, 1135, 1072, 1011, 955, 901,
    850, 803, 757, 715, 675, 637, 601, 567, 535, 505,
    477, 450, 425, 401, 378, 357, 337, 318, 300, 283,
    267, 252, 238,
};

#define TIMER0_OFFSET (-11)
#define TIMER1_OFFSET (0)

// As a whole this register indicates an index in the PWM_LEVELS array.
// - 0:1 indicate the current level of the output for each channel
// - 2:3 indicate the current volume level (0-3)
// to slightly reduce interrupt latency, a general purpose I/O register is used
// since it allows single cycle access.
#define out_level GPIOR0

void impl_setup(void) {
    // buzzer outputs (OCR2A & OCR2B)
    DDRB |= _BV(PB3);
#if HBRIDGE_OUTPUT
    DDRD |= _BV(PD3);
#endif
    PORTD |= _BV(PD3);

    // Timer 0: CTC mode, prescaler=256
    TCCR0A = _BV(WGM01);
    TCCR0B = _BV(CS02);

    // Timer 1: CTC mode, prescaler=8
    TCCR1A = 0;
    TCCR1B = _BV(WGM12) | _BV(CS11);

    // Timer 2: fast PWM mode, prescaler=1
    OCR2A = 255;
#if HBRIDGE_OUTPUT
    OCR2B = 255;
    TCCR2A = _BV(COM2A1) | _BV(COM2B0) | _BV(COM2B1) | _BV(WGM20) | _BV(WGM21);
#else
    TCCR2A = _BV(COM2A1) | _BV(WGM20) | _BV(WGM21);
#endif
    TCCR2B = _BV(CS20);

    sei();
}

void impl_reset(void) {
    OCR2A = 255;
#if HBRIDGE_OUTPUT
    OCR2B = 255;
#endif
    TIMSK0 &= ~_BV(OCIE0A);
    TIMSK1 &= ~_BV(OCIE1A);
    out_level = VOLUME_LEVEL << MAX_CHANNELS;
}

void impl_play_note(const track_t* track, uint8_t channel) {
    bool has_note = track->note != NO_NOTE;
    if (channel == 0) {
        // Timer 0
        if (has_note) {
            OCR0A = TIMER0_NOTES[track->note + TIMER0_OFFSET];
            TIMSK0 |= _BV(OCIE0A);
        } else {
            TIMSK0 &= ~_BV(OCIE0A);
            // set output level to zero. ideally only the track that stoppped playing should be turned
            // off but interrupts are frequent enough that this doesn't matter.
            out_level = VOLUME_LEVEL << MAX_CHANNELS;
        }
    } else {
        // Timer 1
        if (has_note) {
            OCR1A = TIMER1_NOTES[track->note + TIMER1_OFFSET];
            TIMSK1 |= _BV(OCIE1A);
        } else {
            TIMSK1 &= ~_BV(OCIE1A);
            out_level = VOLUME_LEVEL << MAX_CHANNELS;
        }
    }
}

ISR(TIMER0_COMPA_vect) {
    uint8_t level = out_level;
    level ^= 1 << 0;
    uint8_t pwm_level = PWM_LEVELS[level];
    OCR2A = pwm_level;
#if HBRIDGE_OUTPUT
    OCR2B = pwm_level;
#endif
    out_level = level;
}

ISR(TIMER1_COMPA_vect) {
    uint8_t level = out_level;
    level ^= 1 << 1;
    uint8_t pwm_level = PWM_LEVELS[level];
    OCR2A = pwm_level;
#if HBRIDGE_OUTPUT
    OCR2B = pwm_level;
#endif
    out_level = level;
}

#endif // TARGET_ATMEGA328P