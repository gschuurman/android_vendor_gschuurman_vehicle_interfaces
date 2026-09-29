package com.gschuurman.caraudiotuner;

import android.os.Bundle;

import androidx.preference.SeekBarPreference;

import com.android.car.ui.preference.PreferenceFragment;

/** Balance (left/right) and fader (rear/front) of the speakers. */
public final class BalanceFaderFragment extends PreferenceFragment {
    private static final String KEY_CENTER = "center";

    private CarAudioParams.DataStore mDataStore;
    private SeekBarPreference mBalance;
    private SeekBarPreference mFader;

    @Override
    public void onCreatePreferences(Bundle savedInstanceState, String rootKey) {
        mDataStore = new CarAudioParams(requireContext()).new DataStore();
        getPreferenceManager().setPreferenceDataStore(mDataStore);
        setPreferencesFromResource(R.xml.balance_fader_settings, rootKey);

        mBalance = findPreference(CarAudioParams.BALANCE);
        mFader = findPreference(CarAudioParams.FADER);
        mBalance.setOnPreferenceChangeListener((p, value) -> {
            updateSummaries((Integer) value, mFader.getValue());
            return true;
        });
        mFader.setOnPreferenceChangeListener((p, value) -> {
            updateSummaries(mBalance.getValue(), (Integer) value);
            return true;
        });
        findPreference(KEY_CENTER).setOnPreferenceClickListener(p -> {
            mBalance.setValue(0);
            mFader.setValue(0);
            updateSummaries(0, 0);
            return true;
        });
    }

    @Override
    public void onResume() {
        super.onResume();
        mBalance.setValue(mDataStore.getInt(CarAudioParams.BALANCE, 0));
        mFader.setValue(mDataStore.getInt(CarAudioParams.FADER, 0));
        updateSummaries(mBalance.getValue(), mFader.getValue());
    }

    private void updateSummaries(int balance, int fader) {
        mBalance.setSummary(describe(balance, R.string.balance_left, R.string.balance_right));
        mFader.setSummary(describe(fader, R.string.fader_rear, R.string.fader_front));
    }

    private String describe(int value, int negativeRes, int positiveRes) {
        if (value == 0) return getString(R.string.centered);
        final int percent = Math.abs(value) * 100 / CarAudioParams.BALANCE_FADER_STEPS;
        return getString(value < 0 ? negativeRes : positiveRes, percent);
    }
}
