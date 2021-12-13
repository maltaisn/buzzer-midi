#ifndef DEFS_H
#define DEFS_H

#if defined(__AVR_ATmega328P__)
#define MAX_TRACKS 6
#elif defined(__AVR_ATmega3208__)
#define MAX_TRACKS 3
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
