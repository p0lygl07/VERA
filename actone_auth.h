#ifndef ACTONE_AUTH_H
#define ACTONE_AUTH_H

#include "actone.h"
#include <stdbool.h>
#include <stdint.h>

/*
 * Auth band: continues the octave-doubling pattern (110/220/440/880)
 * with root 1760 Hz, 16 symbols (one hex digit each) at
 * f(n) = 1760 * 2^(n/12), n = 0..15.
 *
 * A secure frame is: [command tone] [gap] [auth symbol]x3 [gap]
 * 3 hex-digit symbols = 12 bits = 4096 possible codes per counter
 * value.
 */
#define ACTONE_AUTH_BAND_ROOT_HZ 1760.0f
#define ACTONE_AUTH_SYMBOLS 16
#define ACTONE_AUTH_CODE_SYMBOLS 3  /* 3 x 4 bits = 12-bit truncated HMAC */
#define ACTONE_AUTH_WINDOW 5        /* tolerate up to 5 missed transmissions */
#define ACTONE_AUTH_MAX_FAILURES 5  /* consecutive failures before lockout */
#define ACTONE_AUTH_LOCKOUT_SECONDS 30

typedef struct {
    uint8_t key[32];
    size_t key_len;
    uint64_t counter;          /* next counter value we expect/will send */
    int consecutive_failures;
    double lockout_until;      /* wall-clock time (caller-supplied) */
} actone_auth_ctx_t;

void actone_auth_init(actone_auth_ctx_t *ctx, const uint8_t *key, size_t key_len,
                       uint64_t starting_counter);

float actone_auth_freq_hz(int symbol); /* symbol 0-15 */

/* Compute the 3-symbol auth code for a given (counter, command) pair
 * -- binding the command into the code is what stops a captured
 * frame's auth tones from being spliced onto a different command's
 * tone. out must have room for ACTONE_AUTH_CODE_SYMBOLS ints (each 0-15). */
void actone_auth_compute_code(const actone_auth_ctx_t *ctx, uint64_t counter,
                               actone_cmd_t cmd, int out_symbols[ACTONE_AUTH_CODE_SYMBOLS]);

/*
 * Sender side: generate a secure frame's full PCM buffer (command
 * tone + gap + 3 auth-symbol tones + gap) for the given command,
 * using ctx->counter, then advances ctx->counter by 1.
 * `buf` must be large enough for the whole frame; returns the number
 * of samples actually written.
 */
size_t actone_auth_generate_frame(actone_auth_ctx_t *ctx, actone_cmd_t cmd,
                                    int sample_rate, int16_t *buf, size_t buf_capacity);

typedef enum {
    ACTONE_AUTH_OK = 0,
    ACTONE_AUTH_BAD_MAC,       /* auth code didn't match any counter in the window */
    ACTONE_AUTH_NO_COMMAND,    /* couldn't even decode a command tone */
    ACTONE_AUTH_LOCKED_OUT,    /* too many recent failures, cooling down */
} actone_auth_result_t;

typedef struct {
    actone_auth_result_t result;
    actone_cmd_t cmd;          /* only meaningful if result == ACTONE_AUTH_OK */
    uint64_t matched_counter;  /* only meaningful if result == ACTONE_AUTH_OK */
} actone_auth_decoded_t;

/*
 * Stateless variant of decode_frame: checks the buffer against the
 * counter window WITHOUT touching ctx (no counter advance, no failure
 * tracking, no lockout check/consult). Use this to scan many candidate
 * offsets in a rolling capture buffer -- since most offsets won't even
 * contain a command-shaped tone (NO_COMMAND) and cost nothing toward
 * lockout, and only a genuine command-shaped-but-wrong-MAC result
 * (BAD_MAC) should ever count as a real authentication attempt.
 * Once a caller finds an OK offset via this, call the real
 * actone_auth_decode_frame on that exact slice to consume the counter.
 */
actone_auth_decoded_t actone_auth_peek_frame(const actone_auth_ctx_t *ctx,
                                               const int16_t *buf, size_t num_samples,
                                               int sample_rate);

/*
 * Receiver side: decode a secure frame. `now` is wall-clock time
 * (caller-supplied, e.g. from time(NULL)) used for lockout tracking.
 * On success, advances ctx->counter past the matched value so the
 * same frame can never validate again.
 */
actone_auth_decoded_t actone_auth_decode_frame(actone_auth_ctx_t *ctx,
                                                 const int16_t *buf, size_t num_samples,
                                                 int sample_rate, double now);

#endif /* ACTONE_AUTH_H */
