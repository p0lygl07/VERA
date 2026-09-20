#include "actone.h"
#include "actone_auth.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#define SAMPLE_RATE 8000
#define FRAME_SAMPLES 4160     /* one full secure frame at 8kHz */
#define SCAN_STEP 200          /* offset step size for the sliding search (~25ms) */
#define STREAM_MS 1500         /* total simulated "continuous audio" length */
#define STREAM_SAMPLES (SAMPLE_RATE * STREAM_MS / 1000)

static const uint8_t TEST_KEY[] = "kyger-suit-shared-secret-v1";

/*
 * Scan a buffer at many offsets using the STATELESS peek function, and
 * only call the real stateful decode once on whichever offset actually
 * matched -- mirroring exactly what vera_perception.py's actone_loop
 * needs to do against a rolling capture buffer.
 */
static actone_auth_decoded_t scan_for_frame(actone_auth_ctx_t *ctx,
                                              const int16_t *buf, size_t buf_len,
                                              int sample_rate, double now,
                                              size_t *found_offset) {
    actone_auth_decoded_t empty = {0};
    if (now < ctx->lockout_until) {
        empty.result = ACTONE_AUTH_LOCKED_OUT;
        return empty;
    }

    for (size_t offset = 0; offset + FRAME_SAMPLES <= buf_len; offset += SCAN_STEP) {
        actone_auth_decoded_t peek = actone_auth_peek_frame(ctx, buf + offset,
                                                              FRAME_SAMPLES, sample_rate);
        if (peek.result == ACTONE_AUTH_OK) {
            /* Found it -- now consume it for real (advances counter,
             * resets failure count) via the exact matching slice. */
            *found_offset = offset;
            return actone_auth_decode_frame(ctx, buf + offset, FRAME_SAMPLES,
                                              sample_rate, now);
        }
        if (peek.result == ACTONE_AUTH_BAD_MAC) {
            /* A real command-shaped tone that failed auth at this offset
             * -- feed it through the stateful path too, so failure
             * tracking / lockout behaves exactly as if we'd found this
             * on the first (and only) real attempt. */
            actone_auth_decoded_t real = actone_auth_decode_frame(ctx, buf + offset,
                                                                    FRAME_SAMPLES,
                                                                    sample_rate, now);
            if (real.result == ACTONE_AUTH_LOCKED_OUT) {
                *found_offset = offset;
                return real;
            }
            /* else: BAD_MAC recorded, keep scanning */
        }
    }
    empty.result = ACTONE_AUTH_NO_COMMAND; /* nothing matched anywhere in the scan */
    return empty;
}

int main(void) {
    printf("=== Realistic test: burst at a RANDOM unaligned offset in a continuous stream ===\n\n");

    srand(12345);
    int all_ok = 1;

    for (int trial = 0; trial < 5; trial++) {
        actone_auth_ctx_t sender, receiver;
        actone_auth_init(&sender, TEST_KEY, sizeof(TEST_KEY) - 1, 100 + trial * 100);
        actone_auth_init(&receiver, TEST_KEY, sizeof(TEST_KEY) - 1, 100 + trial * 100);

        /* Build a "continuous audio stream" buffer: random noise
         * everywhere, with one real frame dropped in at a random
         * offset -- simulating a burst that starts at an arbitrary
         * moment relative to when the receiver started listening. */
        int16_t stream[STREAM_SAMPLES];
        for (int i = 0; i < STREAM_SAMPLES; i++) {
            stream[i] = (int16_t)((rand() % 2000) - 1000); /* background noise */
        }

        size_t max_start = STREAM_SAMPLES - FRAME_SAMPLES - 1;
        size_t true_offset = (size_t)(rand() % (int)max_start);

        actone_cmd_t sent_cmd = (actone_cmd_t)(trial % CMD_COUNT);
        int16_t frame_buf[FRAME_SAMPLES];
        actone_auth_generate_frame(&sender, sent_cmd, SAMPLE_RATE, frame_buf, FRAME_SAMPLES);
        memcpy(stream + true_offset, frame_buf, FRAME_SAMPLES * sizeof(int16_t));

        size_t found_offset = 0;
        actone_auth_decoded_t result = scan_for_frame(&receiver, stream, STREAM_SAMPLES,
                                                        SAMPLE_RATE, (double)trial, &found_offset);

        int ok = (result.result == ACTONE_AUTH_OK && result.cmd == sent_cmd);
        all_ok &= ok;
        printf("Trial %d: true_offset=%5zu found_offset=%5zu sent=%-12s decoded=%-12s %s\n",
               trial, true_offset, found_offset, ACTONE_NAME[sent_cmd],
               result.result == ACTONE_AUTH_OK ? ACTONE_NAME[result.cmd] : "NONE",
               ok ? "PASS" : "FAIL");
    }

    printf("\n%s\n", all_ok ? "Sliding-window detection works against realistic unaligned bursts."
                            : "SOME TRIALS FAILED.");
    return all_ok ? 0 : 1;
}
