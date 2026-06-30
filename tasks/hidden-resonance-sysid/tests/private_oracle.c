#include <ctype.h>
#include <errno.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifndef HORIZON_LIMIT
#define HORIZON_LIMIT 2.0
#endif

#define NUM_MODELS 3
#define STATE_N 5
#define BASE_DT 0.001
#define U_MAX 1.0
#define ENERGY_MAX 2.0
#define MAX_SAMPLES 8000

typedef struct {
    double ad[STATE_N * STATE_N];
    double bd[STATE_N];
    double c[STATE_N];
    double d;
} Model;

static const Model MODELS[NUM_MODELS] = {
    {
        .ad = {0.99800199866733308, 0, 0, 0, 0, 0, 0.99999550449999797, 0.00099850000112432506, 0, 0, 0, -0.008986500010118928, 0.99700000449662496, 0, 0, 0, 0, 0, 0.99848854631681583, 0.000998836532455207, 0, 0, 0, -3.0214805106770011, 0.99717008209397495},
        .bd = {0.00099900066633346659, 4.995000002248874e-07, 0.00099850000112432506, 1.209162946547374e-05, 0.024171844085416002},
        .c = {1, 1, 0, 1, 0},
        .d = 0.0
    },
    {
        .ad = {0.99800199866733308, 0, 0, 0, 0, 0, 0.99999550449999797, 0.00099850000112432506, 0, 0, 0, -0.008986500010118928, 0.99700000449662496, 0, 0, 0, 0, 0, 0.99680341119525739, 0.00099813495376169172, 0, 0, 0, -6.3880637040748276, 0.99520639526923871},
        .bd = {0.00099900066633346659, 4.995000002248874e-07, 0.00099850000112432506, 1.9179532828455488e-05, 0.038328382224448961},
        .c = {1, 1, 0, 1, 0},
        .d = 0.0
    },
    {
        .ad = {0.99800199866733308, 0, 0, 0, 0, 0, 0.99999550449999797, 0.00099850000112432506, 0, 0, 0, -0.008986500010118928, 0.99700000449662496, 0, 0, 0, 0, 0, 0.99396318180280674, 0.00099623015975950865, 0, 0, 0, -12.054384933090056, 0.99045645164045326},
        .bd = {0.00099900066633346659, 4.995000002248874e-07, 0.00099850000112432506, 3.0184090985966436e-05, 0.06027192466545029},
        .c = {1, 1, 0, 1, 0},
        .d = 0.0
    },
};

static char *read_all(const char *path) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    if (fseek(f, 0, SEEK_END) != 0) { fclose(f); return NULL; }
    long size = ftell(f);
    if (size < 0) { fclose(f); return NULL; }
    rewind(f);
    char *buf = (char *)calloc((size_t)size + 1, 1);
    if (!buf) { fclose(f); return NULL; }
    if (fread(buf, 1, (size_t)size, f) != (size_t)size) {
        free(buf);
        fclose(f);
        return NULL;
    }
    fclose(f);
    return buf;
}

static char *skip_ws(char *p) {
    while (*p && (isspace((unsigned char)*p) || *p == ',')) ++p;
    return p;
}

static int parse_payload(const char *path, double *dt_out, double *values, int *n_out) {
    char *buf = read_all(path);
    if (!buf) {
        fprintf(stderr, "could not read input\n");
        return 2;
    }
    char *dt_key = strstr(buf, "\"dt\"");
    char *u_key = strstr(buf, "\"u\"");
    if (!dt_key || !u_key) {
        fprintf(stderr, "missing dt or u\n");
        free(buf);
        return 2;
    }
    char *colon = strchr(dt_key, ':');
    if (!colon) {
        free(buf);
        return 2;
    }
    errno = 0;
    double dt = strtod(colon + 1, NULL);
    if (errno || !isfinite(dt) || dt < BASE_DT - 1e-12) {
        fprintf(stderr, "bad dt\n");
        free(buf);
        return 2;
    }
    double ratio = dt / BASE_DT;
    long mult = lround(ratio);
    if (mult < 1 || fabs(dt - ((double)mult) * BASE_DT) > 1e-10) {
        fprintf(stderr, "dt must be an integer multiple of 0.001\n");
        free(buf);
        return 2;
    }
    char *open = strchr(u_key, '[');
    if (!open) {
        free(buf);
        return 2;
    }
    int n = 0;
    double energy = 0.0;
    char *p = open + 1;
    while (*p && *p != ']') {
        p = skip_ws(p);
        if (*p == ']') break;
        char *end = NULL;
        errno = 0;
        double value = strtod(p, &end);
        if (errno || end == p || !isfinite(value)) {
            fprintf(stderr, "bad u\n");
            free(buf);
            return 2;
        }
        if (n >= MAX_SAMPLES) {
            fprintf(stderr, "too many samples\n");
            free(buf);
            return 2;
        }
        if (fabs(value) > U_MAX + 1e-12) {
            fprintf(stderr, "amplitude cap exceeded\n");
            free(buf);
            return 2;
        }
        values[n++] = value;
        energy += value * value * dt;
        p = end;
    }
    if (n <= 0 || ((double)n) * dt > HORIZON_LIMIT + 1e-12) {
        fprintf(stderr, "horizon rejected\n");
        free(buf);
        return 42;
    }
    if (energy > ENERGY_MAX + 1e-12) {
        fprintf(stderr, "energy cap exceeded\n");
        free(buf);
        return 2;
    }
    *dt_out = dt;
    *n_out = n;
    free(buf);
    return 0;
}

static double output_value(const Model *m, const double *x, double u) {
    double y = m->d * u;
    for (int i = 0; i < STATE_N; ++i) {
        y += m->c[i] * x[i];
    }
    return y;
}

static void step_base(const Model *m, double *x, double u) {
    double next[STATE_N];
    for (int i = 0; i < STATE_N; ++i) {
        double acc = m->bd[i] * u;
        for (int j = 0; j < STATE_N; ++j) {
            acc += m->ad[i * STATE_N + j] * x[j];
        }
        next[i] = acc;
    }
    for (int i = 0; i < STATE_N; ++i) {
        x[i] = next[i];
    }
}

static int write_response(const char *path, const Model *m, double dt, const double *values, int n) {
    FILE *out = fopen(path, "wb");
    if (!out) {
        fprintf(stderr, "could not write output\n");
        return 2;
    }
    long mult = lround(dt / BASE_DT);
    double x[STATE_N] = {0, 0, 0, 0, 0};
    fprintf(out, "{\"t\":[");
    for (int i = 0; i < n; ++i) {
        if (i) fprintf(out, ",");
        fprintf(out, "%.17g", ((double)i) * dt);
    }
    fprintf(out, "],\"y\":[");
    for (int i = 0; i < n; ++i) {
        if (i) fprintf(out, ",");
        fprintf(out, "%.17g", output_value(m, x, values[i]));
        for (long k = 0; k < mult; ++k) {
            step_base(m, x, values[i]);
        }
    }
    fprintf(out, "]}\n");
    fclose(out);
    return 0;
}

int main(int argc, char **argv) {
    if (argc != 4) {
        fprintf(stderr, "usage: oracle instance input.json output.json\n");
        return 2;
    }
    char *end = NULL;
    long instance = strtol(argv[1], &end, 10);
    if (!end || *end || instance < 0 || instance >= NUM_MODELS) {
        fprintf(stderr, "bad instance\n");
        return 2;
    }
    double values[MAX_SAMPLES];
    double dt = 0.0;
    int n = 0;
    int rc = parse_payload(argv[2], &dt, values, &n);
    if (rc != 0) {
        return rc;
    }
    return write_response(argv[3], &MODELS[instance], dt, values, n);
}
