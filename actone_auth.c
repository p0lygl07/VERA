#include "actone_auth.h"
#include "sha256.h"
#include <math.h>
#include <string.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

void actone_auth_init(actone_auth_ctx_t *ctx, const uint8_t *key, size_t key_len,
                       uint64_t starting_counter) {
    memset(ctx, 0, sizeof(*ctx));
    size_t n = key_len > sizeof(ctx->key) ? sizeof(ctx->key) : key_len;
    memcpy(ctx->key, key, n);
    ctx->key_len = n;
    ctx->counter = starting_counter;
    ctx->consecutive_failures = 0;
    ctx->lockout_until = 0.0;
}

float actone_auth_freq_hz(int symbol) {
    return ACTONE_AUTH_BAND_ROOT_HZ * powf(2.0f, (float)symbol / 12.0f);
}

void actone_auth_compute_code(const actone_auth_ctx_t *ctx, uint64_t counter,
                               actone_cmd_t cmd, int out_symbols[ACTONE_AUTH_CODE_SYMBOLS]) {
    uint8_t msg[9];
    for (int i = 0; i < 8; i++) {
        msg[i] = (uint8_t)(counter >> (8 * (7 - i)));
    }
    msg[8] = (uint8_t)cmd; /* bind the auth code to the specific command,
                              so an auth code valid for one command cannot
                              be spliced onto a different command's tone */

    uint8_t mac[32];
    hmac_sha256(ctx->key, ctx->key_len, msg, sizeof(msg), mac);

    uint16_t truncated = ((uint16_t)mac[0] << 4) | (mac[1] >> 4); /* 12 bits */
    for (int i = ACTONE_AUTH_CODE_SYMBOLS - 1; i >= 0; i--) {
        out_symbols[i] = truncated & 0xF;
        truncated >>= 4;
    }
}

/* --- Frame layout (samples) ---
 * [command tone: dur_ms] [gap: gap_ms] [auth sym 0: dur_ms] [gap]
 * [auth sym 1: dur_ms] [gap] [auth sym 2: dur_ms]
 */
#define FRAME_TONE_MS 100
#define FRAME_GAP_MS 40

size_t actone_auth_generate_frame(actone_auth_ctx_t *ctx, actone_cmd_t cmd,
                                    int sample_rate, int16_t *buf, size_t buf_capacity) {
    size_t tone_samples = (size_t)(sample_rate * FRAME_TONE_MS / 1000);
    size_t gap_samples = (size_t)(sample_rate * FRAME_GAP_MS / 1000);
    size_t needed = tone_samples * (1 + ACTONE_AUTH_CODE_SYMBOLS) +
                    gap_samples * ACTONE_AUTH_CODE_SYMBOLS;
    if (needed > buf_capacity) return 0;

    int symbols[ACTONE_AUTH_CODE_SYMBOLS];
    actone_auth_compute_code(ctx, ctx->counter, cmd, symbols);

    size_t pos = 0;
    actone_generate(cmd, sample_rate, buf + pos, tone_samples);
    pos += tone_samples;

    for (int i = 0; i < ACTONE_AUTH_CODE_SYMBOLS; i++) {
        memset(buf + pos, 0, gap_samples * sizeof(int16_t));
        pos += gap_samples;
        actone_generate_tone(actone_auth_freq_hz(symbols[i]), sample_rate,
                              buf + pos, tone_samples);
        pos += tone_samples;
    }

    ctx->counter++;
    return pos;
}

/* Decode a single auth symbol from a slice of samples by finding
 * which of the 16 auth-band frequencies has the most energy. */
static int decode_auth_symbol(const int16_t *buf, size_t n, int sample_rate) {
    int best = -1;
    float best_power = -1.0f;
    for (int s = 0; s < ACTONE_AUTH_SYMBOLS; s++) {
        float p = actone_goertzel_power(buf, n, sample_rate, actone_auth_freq_hz(s));
        if (p > best_power) { best_power = p; best = s; }
    }
    return best;
}

actone_auth_decoded_t actone_auth_decode_frame(actone_auth_ctx_t *ctx,
                                                 const int16_t *buf, size_t num_samples,
                                                 int sample_rate, double now) {
    actone_auth_decoded_t result = {0};

    if (now < ctx->lockout_until) {
        result.result = ACTONE_AUTH_LOCKED_OUT;
        return result;
    }

    /* Stateless core check (does not touch ctx). */
    result = actone_auth_peek_frame(ctx, buf, num_samples, sample_rate);

    if (result.result == ACTONE_AUTH_OK) {
        ctx->counter = result.matched_counter + 1;   /* advance past matched value: no replay */
        ctx->consecutive_failures = 0;
        return result;
    }

    if (result.result == ACTONE_AUTH_BAD_MAC) {
        /* Only a frame that DID decode a command tone but failed the MAC
         * check counts toward lockout -- this is what distinguishes "an
         * attacker/spoofer is guessing" from "the scanner tried an offset
         * that wasn't even command-shaped," which peek_frame already
         * filters out as NO_COMMAND before we get here. */
        ctx->consecutive_failures++;
        if (ctx->consecutive_failures >= ACTONE_AUTH_MAX_FAILURES) {
            ctx->lockout_until = now + ACTONE_AUTH_LOCKOUT_SECONDS;
            ctx->consecutive_failures = 0;
        }
    }

    return result;
}

actone_auth_decoded_t actone_auth_peek_frame(const actone_auth_ctx_t *ctx,
                                               const int16_t *buf, size_t num_samples,
                                               int sample_rate) {
    actone_auth_decoded_t result = {0};

    size_t tone_samples = (size_t)(sample_rate * FRAME_TONE_MS / 1000);
    size_t gap_samples = (size_t)(sample_rate * FRAME_GAP_MS / 1000);
    size_t expected = tone_samples * (1 + ACTONE_AUTH_CODE_SYMBOLS) +
                       gap_samples * ACTONE_AUTH_CODE_SYMBOLS;
    if (num_samples < expected) {
        result.result = ACTONE_AUTH_NO_COMMAND;
        return result;
    }

    /* 1. Decode the command tone (first slice). */
    actone_cmd_t cmd = actone_decode(buf, tone_samples, sample_rate, 1e6f);
    if (cmd >= CMD_COUNT) {
        result.result = ACTONE_AUTH_NO_COMMAND;
        return result;
    }

    /* 2. Decode the 3 auth symbols. */
    size_t pos = tone_samples;
    int received_symbols[ACTONE_AUTH_CODE_SYMBOLS];
    for (int i = 0; i < ACTONE_AUTH_CODE_SYMBOLS; i++) {
        pos += gap_samples;
        received_symbols[i] = decode_auth_symbol(buf + pos, tone_samples, sample_rate);
        pos += tone_samples;
    }

    /* 3. Check against a forward window of counter values, so a few
     *    missed transmissions don't desync sender/receiver. Bound to
     *    (counter, cmd) together -- see actone_auth_compute_code. */
    for (uint64_t c = ctx->counter; c < ctx->counter + ACTONE_AUTH_WINDOW; c++) {
        int expected_symbols[ACTONE_AUTH_CODE_SYMBOLS];
        actone_auth_compute_code(ctx, c, cmd, expected_symbols);
        if (memcmp(expected_symbols, received_symbols, sizeof(expected_symbols)) == 0) {
            result.result = ACTONE_AUTH_OK;
            result.cmd = cmd;
            result.matched_counter = c;
            return result;
        }
    }

    result.result = ACTONE_AUTH_BAD_MAC;
    return result;
}
