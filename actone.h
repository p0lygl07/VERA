/*
 * Secure ACTONE — Acoustic Command Tone protocol with HMAC-based
 * authentication and replay protection
 * -----------------------------------------------------------------
 * Same 21-command tone set as base ACTONE, now followed by a short
 * rolling authentication code so a receiver can tell "a real
 * authorized sender transmitted this" from "some other sound source
 * happened to produce a matching tone."
 *
 * This is authentication + replay protection, not secrecy encryption
 * -- there's nothing to hide in "MOVE_FWD", the command set is public.
 * What matters is that a stray tone, a recording played back later,
 * or a guess can't be accepted as genuine.
 *
 * Mechanism (same idea as a garage-door remote or car key fob):
 *   - Sender and receiver share a secret key, provisioned once
 *     out-of-band (NOT over audio), plus a synchronized counter.
 *   - Each command is followed by 3 extra tone symbols encoding
 *     HMAC-SHA256(key, counter) truncated to 12 bits.
 *   - Receiver checks its own counter and a small forward window
 *     (to tolerate a few missed transmissions), and only accepts a
 *     match -- then advances its counter past it, so the same burst
 *     can never validate twice (replay protection).
 *   - Repeated auth failures trigger a lockout window, closing the
 *     brute-force gap a 12-bit code alone would leave open.
 */

#ifndef ACTONE_H
#define ACTONE_H

#include <stddef.h>
#include <stdint.h>

/*
 * ACTONE — Acoustic Command Tone protocol
 * -----------------------------------------
 * A single-tone-per-command signaling scheme for broadcasting simple
 * instructions between devices over a speaker/microphone pair instead
 * of a network link. Useful as an out-of-band channel for droids,
 * drones, and robot-arm builds that already have a piezo buzzer and
 * an electret mic on board (ESP32 dev boards commonly have both), and
 * it works one-to-many with no pairing step: anything listening in
 * range with a mic just hears the tone.
 *
 * Frequencies are spaced 150 Hz apart starting at 600 Hz, chosen to
 * sit comfortably within the range a small piezo buzzer can actually
 * reproduce and a basic electret mic can pick up (roughly 500-4000 Hz),
 * rather than reaching for ultrasonic ranges most cheap hobby hardware
 * can't reliably transmit or receive.
 */

typedef enum {
    CMD_PING = 0,
    CMD_ACK,
    CMD_NACK,
    CMD_STOP,
    CMD_HOME,
    CMD_MOVE_FWD,
    CMD_MOVE_BACK,
    CMD_TURN_LEFT,
    CMD_TURN_RIGHT,
    CMD_GRAB,
    CMD_RELEASE,
    CMD_LED_ON,
    CMD_LED_OFF,
    CMD_ARM_UP,
    CMD_ARM_DOWN,
    CMD_LAUNCH,
    CMD_LAND,
    CMD_RECORD_START,
    CMD_RECORD_STOP,
    CMD_MODE_MANUAL,
    CMD_MODE_AUTO,
    CMD_COUNT
} actone_cmd_t;

extern const float ACTONE_FREQ_HZ[CMD_COUNT];
extern const char *ACTONE_NAME[CMD_COUNT];

/*
 * Generate `num_samples` of 16-bit PCM sine wave at an arbitrary
 * `freq_hz`, with the same attack/decay envelope as actone_generate.
 * This is the primitive actone_generate and the auth-code tones both
 * build on.
 */
void actone_generate_tone(float freq_hz, int sample_rate,
                           int16_t *buf, size_t num_samples);

/*
 * Generate `num_samples` of 16-bit PCM sine wave for `cmd` at
 * `sample_rate`, with a short linear attack/decay ramp to avoid the
 * audible click a hard-edged tone burst would produce on a buzzer.
 * `buf` must have room for num_samples int16_t values.
 */
void actone_generate(actone_cmd_t cmd, int sample_rate,
                      int16_t *buf, size_t num_samples);

/*
 * Goertzel algorithm: returns the energy of `buf` at `target_hz`,
 * without computing a full FFT. This is the same technique classic
 * DTMF (touch-tone) decoders use, and it's cheap enough to run in a
 * tight loop on a microcontroller.
 */
float actone_goertzel_power(const int16_t *buf, size_t num_samples,
                             int sample_rate, float target_hz);

/*
 * Runs the Goertzel detector against every command's frequency and
 * returns whichever one has the strongest energy, provided it clears
 * `threshold` and beats the runner-up by a healthy margin. Returns
 * CMD_COUNT if nothing qualifies (i.e. "no command detected").
 */
actone_cmd_t actone_decode(const int16_t *buf, size_t num_samples,
                            int sample_rate, float threshold);

#endif /* ACTONE_H */
