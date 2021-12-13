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

// Output notes from six different tracks at the same time using
// each timer (timer0, timer1, timer2) for two tracks.
// Output is done on port D (D2, D3, D4, D5, D6 & D7).

#ifdef __AVR_ATmega328P__

#include <avr/io.h>
#include <avr/interrupt.h>

#include <music.h>
#include <util/atomic.h>

#define NO_NOTE_COUNT 0xff

// this array contains timer counts to play each note.
// the same array is used for all timers, but with different offsets, since timers
// only differ by their prescaler.
// timer counts are calculated using the following formula:
//   [count] = round([f_cpu] / [prescaler] / [note frequency] / 2) - 1
_FLASH uint16_t TIMER_NOTES[] = {
    1910, 1803, 1702, 1606, 1516, 1431, 1350, 1275, 1203, 1135, 1072, 1011,
    955, 901, 850, 803, 757, 715, 675, 637, 601, 567, 535, 505,
    477, 450, 425, 401, 378, 357, 337, 318, 300, 283, 267, 252,
    238, 224, 212, 200, 189, 178, 168, 158, 149, 141, 133, 126,
    118, 112, 105, 99, 94, 88, 83, 79, 74, 70, 66, 62,
    59, 55, 52, 49, 46, 44, 41, 39, 37, 35, 33, 31,
    29, 27, 26, 24, 23, 21, 20, 19, 18, 17, 16, 15,
    14, 13, 12,
};

// offset in TIMER_NOTES array minus first playable note
#define TIMER0_OFFSET (35 - 11)
#define TIMER1_OFFSET (0 - 0)
#define TIMER2_OFFSET (35 - 23)

#define TRACK0_ADJUST 1
#define TRACK1_ADJUST 1
#define TRACK2_ADJUST 0
#define TRACK3_ADJUST 2
#define TRACK4_ADJUST 1
#define TRACK5_ADJUST 0

// GPIOR0 is accessible with SBI.
// A register could have also been used.
#define notes_on GPIOR0

// current timer count for each track, or NO_NOTE_COUNTx if no note playing.
static uint8_t timer_cnt0 = NO_NOTE_COUNT;
static uint8_t timer_cnt1 = NO_NOTE_COUNT;
static uint16_t timer_cnt2 = NO_NOTE_COUNT;
static uint16_t timer_cnt3 = NO_NOTE_COUNT;
static uint8_t timer_cnt4 = NO_NOTE_COUNT;
static uint8_t timer_cnt5 = NO_NOTE_COUNT;

// timer count for currently playing note, or NO_NOTE_COUNTx if no note playing.
static uint8_t timer_note0;
static uint8_t timer_note1;
static uint16_t timer_note2;
static uint16_t timer_note3;
static uint8_t timer_note4;
static uint8_t timer_note5;

void impl_setup(void) {
    // buzzer outputs
    DDRD |= _BV(PD2) | _BV(PD3) | _BV(PD4) | _BV(PD5) | _BV(PD6) | _BV(PD7);
    DDRB |= _BV(PB5);

    // set timer 0: CTC mode (2), 256 prescaler, compare output match A interrupt
    TCCR0A = _BV(WGM01);
    TCCR0B = _BV(CS02);
    TIMSK0 = _BV(OCIE0A);
    OCR0A = NO_NOTE_COUNT;

    // set timer 1: CTC mode (4), 64 prescaler, compare output match A interrupt
    TCCR1A = 0;
    TCCR1B = _BV(WGM12) | _BV(CS11) | _BV(CS10);
    TIMSK1 = _BV(OCIE1A);
    OCR1A = NO_NOTE_COUNT;

    // set timer 2: CTC mode (2), 128 prescaler, compare output match A interrupt
    TCCR2A = _BV(WGM21);
    TCCR2B = _BV(CS22) | _BV(CS20);
    TIMSK2 = _BV(OCIE2A);
    OCR2A = NO_NOTE_COUNT;

    sei();
}

void impl_reset(void) {
    notes_on = 0;
}

void impl_play_note(const track_t* track, uint8_t track_num) {
    // - set or clear bit on notes_on bit-field
    // - update timer compare match timer_notex (or NO_NOTE_COUNTx if no note playing)
    // - initialize current timer count to timer note count
    // - initialize timer compare match to timer note count
    // - when not playing note, set buzzer output low or high, depending on
    //   the type of transistor that was used in the circuit (P or N), in order to
    //   reduce current consumption when the buzzer is turned off.
    bool has_note = track->note != NO_NOTE;
    ATOMIC_BLOCK(ATOMIC_FORCEON) {
        if (has_note) {
            notes_on |= _BV(track_num);
        } else {
            notes_on &= ~_BV(track_num);
        }
        switch (track_num) {
            case 0: {
                timer_note0 = has_note ? TIMER_NOTES[track->note + TIMER0_OFFSET] : NO_NOTE_COUNT;
                timer_cnt0 = timer_note0;
                OCR0A = timer_note0;
                PORTD |= _BV(PD2);
                break;
            }
            case 1: {
                timer_note1 = has_note ? TIMER_NOTES[track->note + TIMER0_OFFSET] : NO_NOTE_COUNT;
                timer_cnt1 = timer_note1;
                OCR0A = timer_note1;
                PORTD |= _BV(PD3);
                break;
            }
            case 2: {
                timer_note2 = has_note ? TIMER_NOTES[track->note + TIMER1_OFFSET] : NO_NOTE_COUNT;
                timer_cnt2 = timer_note2;
                OCR1A = timer_note2;
                PORTD |= _BV(PD4);
                break;
            }
            case 3: {
                timer_note3 = has_note ? TIMER_NOTES[track->note + TIMER1_OFFSET] : NO_NOTE_COUNT;
                timer_cnt3 = timer_note3;
                OCR1A = timer_note3;
                PORTD |= _BV(PD5);
                break;
            }
            case 4: {
                timer_note4 = has_note ? TIMER_NOTES[track->note + TIMER2_OFFSET] : NO_NOTE_COUNT;
                timer_cnt4 = timer_note4;
                OCR2A = timer_note4;
                PORTD |= _BV(PD6);
                break;
            }
            case 5: {
                timer_note5 = has_note ? TIMER_NOTES[track->note + TIMER2_OFFSET] : NO_NOTE_COUNT;
                timer_cnt5 = timer_note5;
                OCR2A = timer_note5;
                PORTD |= _BV(PD7);
                break;
            }
            default:
                break;
        }
    }
}

// All ISRs follow the same principle. Each timer controls two tracks
// so a separate timer count is kept for each track. The actual timer
// count is set to the lowest of those two, at all times. When the
// interrupt is triggered, both counts are decremented by the current
// timer period to account for elapsed time since last interrupt. Then,
// if any of those two counts are zero, the corresponding buzzer output
// is toggled, and the count is reset to the currently played note count value.

// Any change must be made carefully, as to not increase the interrupt
// latency too much (this is particularly true for timer1, for which
// the prescaler is lower and the latency is naturally higher due to
// dealing with 16-bit data). Assembly output should be checked if a
// change is made to ensure this. Notable optimizations here are
// using a global register (r4) for notes_on, caching timer_cntx to
// avoid multiple RAM reads, and making sure to use constructs which
// result in less instructions (e.g. PIND = ... results in 2 instructions
// while PIND |= ... results in a single SBI instruction!).

// Also notice that the track counts are not always set to the note
// count, but sometimes have a TRACKn_ADJUST subtracted.
// This is based on experiment aiming to reduce dissonance when two
// notes with close frequency are being played by the same timer. These
// adjustments are probably influenced by a variety of factors, and
// may need to be adjusted.

ISR(TIMER0_COMPA_vect) {
    uint8_t cnt0 = timer_cnt0;
    uint8_t cnt1 = timer_cnt1;
    uint8_t timer = OCR0A;
    if (notes_on & _BV(0)) {
        cnt0 -= timer;
    }
    if (notes_on & _BV(1)) {
        cnt1 -= timer;
    }
    if (cnt0 == 0) {
        PIND |= _BV(PD2);
        cnt0 = timer_note0;
        if (notes_on & _BV(0)) {
            cnt0 -= TRACK0_ADJUST;
        }
    }
    if (cnt1 == 0) {
        PIND |= _BV(PD3);
        cnt1 = timer_note1;
        if (notes_on & _BV(1)) {
            cnt1 -= TRACK1_ADJUST;
        }
    }
    timer_cnt0 = cnt0;
    timer_cnt1 = cnt1;
    OCR0A = cnt0 < cnt1 ? cnt0 : cnt1;
}

ISR(TIMER1_COMPA_vect) {
    uint16_t cnt2 = timer_cnt2;
    uint16_t cnt3 = timer_cnt3;
    uint16_t timer = OCR1A;
    if (notes_on & _BV(2)) {
        cnt2 -= timer;
    }
    if (notes_on & _BV(3)) {
        cnt3 -= timer;
    }
    if (cnt2 == 0) {
        PIND |= _BV(PD4);
        cnt2 = timer_note2;
        if (notes_on & _BV(2)) {
            cnt2 -= TRACK2_ADJUST;
        }
    }
    if (cnt3 == 0) {
        PIND |= _BV(PD5);
        cnt3 = timer_note3;
        if (notes_on & _BV(3)) {
            cnt3 -= TRACK3_ADJUST;
        }
    }
    timer_cnt2 = cnt2;
    timer_cnt3 = cnt3;
    OCR1A = cnt2 < cnt3 ? cnt2 : cnt3;
}

ISR(TIMER2_COMPA_vect) {
    uint8_t cnt4 = timer_cnt4;
    uint8_t cnt5 = timer_cnt5;
    uint8_t timer = OCR2A;
    if (notes_on & _BV(4)) {
        cnt4 -= timer;
    }
    if (notes_on & _BV(5)) {
        cnt5 -= timer;
    }
    if (cnt4 == 0) {
        PIND |= _BV(PD6);
        cnt4 = timer_note4;
        if (notes_on & _BV(4)) {
            cnt4 -= TRACK4_ADJUST;
        }
    }
    if (cnt5 == 0) {
        PIND |= _BV(PD7);
        cnt5 = timer_note5;
        if (notes_on & _BV(5)) {
            cnt5 -= TRACK5_ADJUST;
        }
    }
    timer_cnt4 = cnt4;
    timer_cnt5 = cnt5;
    OCR2A = cnt4 < cnt5 ? cnt4 : cnt5;
}

#endif