package com.gschuurman.caraudiotuner;

import android.os.Bundle;

import androidx.preference.ListPreference;
import androidx.preference.SeekBarPreference;

import com.android.car.ui.preference.PreferenceFragment;

/** Equalizer settings: on/off, a preset and the gain of each band. */
public final class EqualizerFragment extends PreferenceFragment {
    private static final String KEY_PRESET = "preset";
    private static final String KEY_RESET = "reset";

    private CarAudioParams mParams;
    private CarAudioParams.DataStore mDataStore;

    @Override
    public void onCreatePreferences(Bundle savedInstanceState, String rootKey) {
        mParams = new CarAudioParams(requireContext());
        mDataStore = mParams.new DataStore();
        getPreferenceManager().setPreferenceDataStore(mDataStore);
        setPreferencesFromResource(R.xml.equalizer_settings, rootKey);

        final ListPreference preset = findPreference(KEY_PRESET);
        // The preset only fills in the bands; it isn't stored.
        preset.setPreferenceDataStore(null);
        preset.setPersistent(false);
        preset.setOnPreferenceChangeListener((p, value) -> {
            applyPreset(Integer.parseInt((String) value));
            return false;
        });
        for (int band = 0; band < CarAudioParams.EQ_BANDS; ++band) {
            findPreference(CarAudioParams.eqBand(band)).setOnPreferenceChangeListener((p, value) -> {
                p.setSummary(getString(R.string.eq_gain, (Integer) value));
                return true;
            });
        }
        findPreference(KEY_RESET).setOnPreferenceClickListener(p -> {
            setBands(new int[CarAudioParams.EQ_BANDS]);
            return true;
        });
    }

    @Override
    public void onResume() {
        super.onResume();
        // The HAL is the source of truth; show its current values.
        for (int band = 0; band < CarAudioParams.EQ_BANDS; ++band) {
            final SeekBarPreference slider = findPreference(CarAudioParams.eqBand(band));
            slider.setValue(mDataStore.getInt(slider.getKey(), 0));
            slider.setSummary(getString(R.string.eq_gain, slider.getValue()));
        }
    }

    private void applyPreset(int index) {
        final String[] gains = getResources().getStringArray(R.array.eq_preset_gains)[index]
                .split(",");
        final int[] bands = new int[CarAudioParams.EQ_BANDS];
        for (int band = 0; band < bands.length; ++band) {
            bands[band] = Integer.parseInt(gains[band].trim());
        }
        setBands(bands);
    }

    private void setBands(int[] gains) {
        for (int band = 0; band < gains.length; ++band) {
            final SeekBarPreference slider = findPreference(CarAudioParams.eqBand(band));
            slider.setValue(gains[band]);  // also writes the parameter
            slider.setSummary(getString(R.string.eq_gain, gains[band]));
        }
    }
}
