#include "actone.h"
#include <math.h>
#include <stdlib.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

/* f(cmd) = 600 + 150 * cmd_index -- one formula, no arbitrary table,
 * same design spirit as the RUNIC LUX band law. */
const float ACTONE_FREQ_HZ[CMD_COUNT] = {
    600.0f, 750.0f, 900.0f, 1050.0f, 1200.0f, 1350.0f, 1500.0f, 1650.0f,
    1800.0f, 1950.0f, 2100.0f, 2250.0f, 2400.0f, 2550.0f, 2700.0f,
    2850.0f, 3000.0f, 3150.0f, 3300.0f, 3450.0f, 3600.0f
};

const char *ACTONE_NAME[CMD_COUNT] = {
    "PING", "ACK", "NACK", "STOP", "HOME",
    "MOVE_FWD", "MOVE_BACK", "TURN_LEFT", "TURN_RIGHT",
    "GRAB", "RELEASE", "LED_ON", "LED_OFF",
    "ARM_UP", "ARM_DOWN", "LAUNCH", "LAND",
    "RECORD_START", "RECORD_STOP", "MODE_MANUAL", "MODE_AUTO"
};

void actone_generate_tone(float freq_hz, int sample_rate,
                           int16_t *buf, size_t num_samples) {
    float amplitude = 30000.0f; /* near int16 max (32767) -- push the transmit
                                   level as high as possible without clipping,
                                   for more real-world margin against distance,
                                   volume, and mic gain variability */

    size_t ramp = num_samples / 20;
    if (ramp > 200) ramp = 200;
    if (ramp < 1) ramp = 1;

    for (size_t i = 0; i < num_samples; i++) {
        float t = (float)i / (float)sample_rate;
        float sample = amplitude * sinf(2.0f * (float)M_PI * freq_hz * t);

        float env = 1.0f;
        if (i < ramp) {
            env = (float)i / (float)ramp;
        } else if (i >= num_samples - ramp) {
            env = (float)(num_samples - i) / (float)ramp;
        }
        buf[i] = (int16_t)(sample * env);
    }
}

void actone_generate(actone_cmd_t cmd, int sample_rate,
                      int16_t *buf, size_t num_samples) {
    if (cmd >= CMD_COUNT) return;
    actone_generate_tone(ACTONE_FREQ_HZ[cmd], sample_rate, buf, num_samples);
}

float actone_goertzel_power(const int16_t *buf, size_t num_samples,
                             int sample_rate, float target_hz) {
    float k = (float)num_samples * target_hz / (float)sample_rate;
    float w = (2.0f * (float)M_PI / (float)num_samples) * k;
    float cosine = cosf(w);
    float coeff = 2.0f * cosine;

    float q0 = 0.0f, q1 = 0.0f, q2 = 0.0f;
    for (size_t i = 0; i < num_samples; i++) {
        q0 = coeff * q1 - q2 + (float)buf[i];
        q2 = q1;
        q1 = q0;
    }
    /* Real magnitude-squared energy at target_hz, normalized by N so
     * results are comparable across different buffer lengths. */
    float real = q1 - q2 * cosine;
    float imag = q2 * sinf(w);
    return (real * real + imag * imag) / ((float)num_samples * (float)num_samples);
}

actone_cmd_t actone_decode(const int16_t *buf, size_t num_samples,
                            int sample_rate, float threshold) {
    float best_power = -1.0f, second_power = -1.0f;
    actone_cmd_t best_cmd = CMD_COUNT;

    for (int c = 0; c < CMD_COUNT; c++) {
        float p = actone_goertzel_power(buf, num_samples, sample_rate,
                                         ACTONE_FREQ_HZ[c]);
        if (p > best_power) {
            second_power = best_power;
            best_power = p;
            best_cmd = (actone_cmd_t)c;
        } else if (p > second_power) {
            second_power = p;
        }
    }

    /* Require the winner to actually clear the noise floor AND beat the
     * runner-up by a healthy margin -- otherwise report "no command",
     * since a false trigger on a physical device is worse than a missed one. */
    if (best_power < threshold) return CMD_COUNT;
    if (second_power > 0 && best_power < second_power * 3.0f) return CMD_COUNT;

    return best_cmd;
}
