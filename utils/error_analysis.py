#!/usr/bin/env python3
import math
import sys

from midi_convert import parse_channels_spec, NOTE_NAMES
from tracks_to_wav import get_note_freq

# from an input channels specification string (same as taken by midi_convert),
# print a few stats showing the actual frequency of the note produced by the buzzer,
# the frequency error, and the error in centi-semitones (?!).


def format_note(bnote: int):
    return f"{NOTE_NAMES[bnote % 12]}{bnote // 12 + 2}"


def main(spec_str: str) -> None:
    # parse specification
    try:
        channels_spec = parse_channels_spec(spec_str)
    except ValueError as e:
        print(e)
        sys.exit(1)

    for i, spec in enumerate(channels_spec):
        # check if any channel is identical
        identical_idx = [j for j in range(0, i) if channels_spec[i] == channels_spec[j]]
        print(f"CHANNEL {i}:")
        if identical_idx:
            print(f"(identical to channel {identical_idx[0]})")
        else:
            print("Number   Note   Target freq (Hz)   Actual freq (Hz)   "
                  "Timer count   Error (Hz)   Error (ct)")
            for bnote in spec.note_range:
                name = format_note(bnote)
                target_freq = get_note_freq(bnote)
                timer_cnt = round(spec.timer_period / target_freq / 2) - 1
                actual_freq = spec.timer_period / (timer_cnt + 1) / 2
                error_freq = actual_freq - target_freq
                error_tone = 12 * math.log2(actual_freq / target_freq) * 100
                print(f"{bnote:^6}   {name:<4}   {target_freq:^16.1f}   {actual_freq:^16.1f}   "
                      f"{timer_cnt:^11}   {error_freq:^+10.1f}   {error_tone:^+10.1f}")

        print()


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Expected one argument")
        sys.exit(1)
    main(sys.argv[1])
