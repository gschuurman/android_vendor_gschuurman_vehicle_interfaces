package com.gschuurman.caraudiotuner;

import android.content.Context;
import android.media.AudioManager;
import android.util.Log;

import androidx.preference.PreferenceDataStore;

/**
 * The car audio settings of the audio HAL, read and written as "car.*" audio parameters. The HAL
 * applies and persists them itself (persist.vendor.audio.car.*), so nothing is stored here.
 */
final class CarAudioParams {
    private static final String TAG = "CarAudioTuner";

    static final String BALANCE = "car.balance";
    static final String FADER = "car.fader";
    static final String EQ_ENABLED = "car.eq.enabled";
    static final int EQ_BANDS = 5;

    /** Balance and fader run from -1 to 1; the sliders use -STEPS..STEPS. */
    static final int BALANCE_FADER_STEPS = 10;

    static String eqBand(int band) {
        return "car.eq.band" + band;
    }

    private final AudioManager mAudioManager;

    CarAudioParams(Context context) {
        mAudioManager = context.getSystemService(AudioManager.class);
    }

    float get(String key, float defaultValue) {
        // The reply looks like "car.balance=0.300000".
        for (String pair : mAudioManager.getParameters(key).split(";")) {
            final int eq = pair.indexOf('=');
            if (eq > 0 && pair.substring(0, eq).equals(key)) {
                try {
                    return Float.parseFloat(pair.substring(eq + 1));
                } catch (NumberFormatException e) {
                    Log.w(TAG, "Bad value for " + key + ": " + pair);
                }
            }
        }
        return defaultValue;
    }

    void set(String key, float value) {
        mAudioManager.setParameters(key + "=" + value);
    }

    /**
     * Maps preferences to the parameters: switches are 0/1, EQ bands are whole dB, balance and
     * fader are scaled to -BALANCE_FADER_STEPS..BALANCE_FADER_STEPS.
     */
    final class DataStore extends PreferenceDataStore {
        @Override
        public boolean getBoolean(String key, boolean defValue) {
            return get(key, defValue ? 1 : 0) != 0;
        }

        @Override
        public void putBoolean(String key, boolean value) {
            set(key, value ? 1 : 0);
        }

        @Override
        public int getInt(String key, int defValue) {
            final float scale = isBalanceOrFader(key) ? BALANCE_FADER_STEPS : 1;
            return Math.round(get(key, defValue / scale) * scale);
        }

        @Override
        public void putInt(String key, int value) {
            set(key, isBalanceOrFader(key) ? (float) value / BALANCE_FADER_STEPS : value);
        }

        private boolean isBalanceOrFader(String key) {
            return BALANCE.equals(key) || FADER.equals(key);
        }
    }
}
