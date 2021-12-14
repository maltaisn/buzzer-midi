#ifndef MAIN_H
#define MAIN_H

#ifndef LOOP
// Whether to loop the music data playback indefinitely.
#define LOOP true
#endif

// Adjustment by 256 us increments to account for time spent
// reading new note data after each 1/32nd of a beat.
// Alternatively, music_loop can be called from a timer interrupt
// with the appropriate period (256 us * music_state.tempo).
#define TEMPO_ADJUST -1

int main(void);

#endif //MAIN_H
