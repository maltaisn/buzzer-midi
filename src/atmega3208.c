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

// ==== 3 channels on 1 buzzer implementation for ATmega3208 ====
//
// Outputs notes from up to 3 channels to a single output connected to a buzzer.
// Optionally, another pin can output the inverted signal for a H-bridge setup.
// Volume control is possible by changing the range of the PWM duty cycle.
//
// The TCA timer is used to output a PWM signal with varying duty cycle.
// If more channels are "on" at a time, the duty cycle is higher and inversely.
// A channel is "on" for half of the period of the note it's playing.
// The current on/off state of a channel is kept in a variable.
// The TCB timers are used to toggle that state and update the PWM duty cycle
// during their interrupt.
//
// The buzzer acts as a low-pass filter so the 50 kHz PWM creates something
// ressembling a 2-bit DAC, with 4 levels of output. The output level is the
// sum of all channel levels at the current time.
//
// It would technically be possible to have up to six channels using the
// same timer multiplexing trick as in the ATmega328P implementation, however
// the sound coming out of buzzer already isn't so good with three channels
// so it would probably not be worth it.
//
// Resources used:
// - TCA0 high timer (split mode, low timer is unused)
// - TCB0, TCB1, TCB2 for 3 channels.
// - 1 event system channel if H-bridge output is enabled.
// - About 150k cycles per second for the interrupts (1.5% usage at 10 MHz).
//   (counting 50 cycles per interrupt, x3, playing a 500 Hz note).

#ifdef __AVR_ATmega3208__

#include <avr/io.h>
#include <avr/interrupt.h>
#include <music.h>

// different volume levels are supported by varying the PWM duty cycle range
// volume is not changeable at runtime in the current implementation but this isn't an issue.
#define VOLUME_LEVEL 2

// Whether to output a pair of differential signals to drive a H-bridge.
// PA3 is the normal output and PA2 is the inverted input.
// if disabled, only PA3 is output.
#define HBRIDGE_OUTPUT 1

// As a whole this register indicates an index in the PWM_LEVELS array.
// - 0:2 indicate the current level of the output for a track
// - 3:4 indicate the current volume level (0-3)
// to slightly reduce interrupt latency, a general purpose I/O register is used
// since it allows single cycle access.
#define out_level GPIOR0

// Timer counts for TCA PWM timer.
// The number corresponds to the number of bits set in the 0-7 position,
// multiplied by an arbitrary constant to account for the volume.
static uint8_t PWM_LEVELS[] = {
    0, 1, 1, 2, 1, 2, 2, 3,     // volume = 0, duty cycle 0 to 12%
    0, 2, 2, 4, 2, 4, 4, 6,     // volume = 1, duty cycle 0 to 24%
    0, 4, 4, 8, 4, 8, 8, 12,    // volume = 2, duty cycle 0 to 48%
    0, 8, 8, 16, 8, 16, 16, 24, // volume = 3, duty cycle 0 to 96%
};

// Timer counts for TCB channel timers, for each playable note.
// Counts are calculated using the following formula:
//   [count] = round([f_cpu] / [prescaler] / [note frequency] / 2) - 1
// Maximum error should be less than 0.1% of a semitone.
static uint16_t TIMER_NOTES[] = {
    38222, 36076, 34051, 32140, 30336, 28634, 27026, 25510, 24078, 22726, 21451, 20247,
    19110, 18038, 17025, 16070, 15168, 14316, 13513, 12754, 12038, 11363, 10725, 10123,
    9555, 9018, 8512, 8034, 7583, 7158, 6756, 6377, 6019, 5681, 5362, 5061,
    4777, 4509, 4256, 4017, 3791, 3578, 3377, 3188, 3009, 2840, 2680, 2530,
    2388, 2254, 2127, 2008, 1895, 1789, 1688, 1593, 1504, 1419, 1340, 1264,
    1193, 1126, 1063, 1003, 947, 894, 844, 796, 751, 709, 669, 632, 596,
};

void impl_setup(void) {
    // 10 MHz clock, using pdiv = 2 on 20 MHz internal oscillator.
    _PROTECTED_WRITE(CLKCTRL.MCLKCTRLB, CLKCTRL_PDIV_2X_gc | CLKCTRL_ENABLE_bm);

    VPORTA.DIR = PIN2_bm | PIN3_bm;

    // Timer A: prescaler 2, split mode, single slope PWM on compare channel 3.
    // PWM is output on PA3 for buzzer. Only high timer is used, low timer is unused.
    TCA0.SPLIT.CTRLD = TCA_SPLIT_SPLITM_bm;
    TCA0.SPLIT.HPER = PWM_LEVELS[sizeof PWM_LEVELS - 1];
    TCA0.SPLIT.HCMP0 = 0;
    TCA0.SPLIT.CTRLB = TCA_SPLIT_HCMP0EN_bm;
    TCA0.SPLIT.CTRLA = TCA_SPLIT_CLKSEL_DIV8_gc | TCA_SPLIT_ENABLE_bm;

    // Timers B: used for each of the 3 music tracks. prescaler = 2, periodic interrupt mode.
    TCB0.CTRLA = TCB_CLKSEL_CLKDIV2_gc;
    TCB0.INTCTRL = TCB_CAPT_bm;

    TCB1.CTRLA = TCB_CLKSEL_CLKDIV2_gc;
    TCB1.INTCTRL = TCB_CAPT_bm;

    TCB2.CTRLA = TCB_CLKSEL_CLKDIV2_gc;
    TCB2.INTCTRL = TCB_CAPT_bm;

#if HBRIDGE_OUTPUT
    // Set the event system channel 0 to PA3, with event user EVOUTA pin (PA2, inverted).
    PORTA.PIN2CTRL = PORT_INVEN_bm;
    EVSYS.CHANNEL0 = EVSYS_GENERATOR_PORT0_PIN3_gc;
    EVSYS.USEREVOUTA = EVSYS_CHANNEL_CHANNEL0_gc;
#endif

    sei();
}

void impl_reset(void) {
    TCA0.SPLIT.HCMP0 = 0;
    TCB0.CTRLA &= ~TCB_ENABLE_bm;
    TCB1.CTRLA &= ~TCB_ENABLE_bm;
    TCB2.CTRLA &= ~TCB_ENABLE_bm;
    out_level = VOLUME_LEVEL << MAX_TRACKS;
}

void impl_play_note(const track_t* track, uint8_t track_num) {
    bool has_note = track->note != NO_NOTE;
    TCB_t* tcb = &TCB0 + track_num;
    if (has_note) {
        tcb->CCMP = TIMER_NOTES[track->note];
        tcb->CTRLA |= TCB_ENABLE_bm;
    } else {
        tcb->CTRLA &= ~TCB_ENABLE_bm;
        // set output level to zero. ideally only the track that stoppped playing should be turned
        // off but interrupts are frequent enough that this doesn't matter.
        out_level = VOLUME_LEVEL << MAX_TRACKS;
    }
}

// TCB interrupts:
// - update track output level bit field
// - update TCA0 PWM duty cycle

ISR(TCB0_INT_vect) {
    uint8_t level = out_level;
    level ^= 1 << 0;
    TCA0.SPLIT.HCMP0 = PWM_LEVELS[level];
    out_level = level;
    TCB0.INTFLAGS = TCB_CAPT_bm;
}

ISR(TCB1_INT_vect) {
    uint8_t level = out_level;
    level ^= 1 << 1;
    TCA0.SPLIT.HCMP0 = PWM_LEVELS[level];
    out_level = level;
    TCB1.INTFLAGS = TCB_CAPT_bm;
}

ISR(TCB2_INT_vect) {
    uint8_t level = out_level;
    level ^= 1 << 2;
    TCA0.SPLIT.HCMP0 = PWM_LEVELS[level];
    out_level = level;
    TCB2.INTFLAGS = TCB_CAPT_bm;
}

#endif