package com.gschuurman.caraudiotuner;

/**
 * Frequency response of the HAL's car equalizer (hardware/amlogic/yukawa/audio
 * primary/CarEqualizer.cpp), so the curve on screen is what is heard: one-octave peaking biquads
 * (Audio EQ Cookbook) plus the preamp, lowered by the HAL so the peak stays at or below 0 dB.
 */
final class EqResponse {
    private static final double Q = Math.sqrt(2);
    private static final double SAMPLE_RATE = 48000;
    private static final int PEAK_SAMPLES = 240;
    private static final double PEAK_MARGIN_DB = 0.1;

    private final double[][] mFilters = new double[CarAudioParams.EQ_BANDS][];
    private double mGainDb;

    /** Sets the band gains and the preamp, all in dB. */
    void set(int[] bandsDb, int preampDb) {
        for (int band = 0; band < CarAudioParams.EQ_BANDS; ++band) {
            mFilters[band] = bandsDb[band] == 0 ? null
                    : peaking(CarAudioParams.EQ_FREQUENCIES_HZ[band], bandsDb[band]);
        }
        mGainDb = 0;
        double peakDb = Double.NEGATIVE_INFINITY;
        final double top = Math.min(20000, 0.45 * SAMPLE_RATE);
        for (int i = 0; i < PEAK_SAMPLES; ++i) {
            peakDb = Math.max(peakDb, responseDb(20 * Math.pow(top / 20, i / (PEAK_SAMPLES - 1.0))));
        }
        for (float f : CarAudioParams.EQ_FREQUENCIES_HZ) peakDb = Math.max(peakDb, responseDb(f));
        peakDb += PEAK_MARGIN_DB;
        mGainDb = preampDb - Math.max(0, preampDb + peakDb);
    }

    /** Response at 'frequencyHz' in dB, including the preamp and the HAL's headroom. */
    double responseDb(double frequencyHz) {
        final double w = 2 * Math.PI * frequencyHz / SAMPLE_RATE;
        // |H(e^-jw)| of each biquad, with z^-1 = cos w - j sin w.
        final double c1 = Math.cos(w), s1 = -Math.sin(w), c2 = Math.cos(2 * w), s2 = -Math.sin(2 * w);
        double db = mGainDb;
        for (double[] f : mFilters) {
            if (f == null) continue;
            final double nr = f[0] + f[1] * c1 + f[2] * c2, ni = f[1] * s1 + f[2] * s2;
            final double dr = 1 + f[3] * c1 + f[4] * c2, di = f[3] * s1 + f[4] * s2;
            db += 10 * Math.log10((nr * nr + ni * ni) / (dr * dr + di * di));
        }
        return db;
    }

    private static double[] peaking(double frequency, double gainDb) {
        final double a = Math.pow(10, gainDb / 40);
        final double w0 = 2 * Math.PI * frequency / SAMPLE_RATE;
        final double alpha = Math.sin(w0) / (2 * Q);
        final double cos = Math.cos(w0);
        final double a0 = 1 + alpha / a;
        return new double[] {(1 + alpha * a) / a0, -2 * cos / a0, (1 - alpha * a) / a0,
                -2 * cos / a0, (1 - alpha / a) / a0};
    }
}
