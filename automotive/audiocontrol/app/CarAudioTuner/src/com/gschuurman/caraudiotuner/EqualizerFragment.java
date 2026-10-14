package com.gschuurman.caraudiotuner;

import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.Switch;

import androidx.fragment.app.Fragment;

import com.android.car.ui.AlertDialogBuilder;

/**
 * Graphic equalizer: on/off, a preamp and the 10 octave bands of the audio HAL, with the resulting
 * frequency response. Every change is written to the HAL right away; the HAL persists it.
 */
public final class EqualizerFragment extends Fragment {
    private static final float DISABLED_ALPHA = 0.4f;

    private CarAudioParams mParams;
    private final EqResponse mResponse = new EqResponse();
    private final int[] mBands = new int[CarAudioParams.EQ_BANDS];
    private int mPreamp;

    private Switch mEnabled;
    private EqCurveView mCurve;
    private EqSliderView mPreampSlider;
    private final EqSliderView[] mBandSliders = new EqSliderView[CarAudioParams.EQ_BANDS];
    private View[] mControls;

    @Override
    public View onCreateView(LayoutInflater inflater, ViewGroup container, Bundle savedInstanceState) {
        return inflater.inflate(R.layout.fragment_equalizer, container, false);
    }

    @Override
    public void onViewCreated(View view, Bundle savedInstanceState) {
        mParams = new CarAudioParams(requireContext());
        mEnabled = view.findViewById(R.id.eq_enabled);
        mCurve = view.findViewById(R.id.eq_curve);
        final Button preset = view.findViewById(R.id.eq_preset);
        final Button reset = view.findViewById(R.id.eq_reset);

        final LinearLayout row = view.findViewById(R.id.eq_sliders);
        mPreampSlider = addSlider(row, getString(R.string.eq_preamp_label));
        mPreampSlider.setOnValueChangeListener((s, value) -> {
            mPreamp = value;
            mParams.set(CarAudioParams.EQ_PREAMP, value);
            updateCurve();
        });
        // A gap between the preamp and the bands.
        row.addView(new View(requireContext()), new LinearLayout.LayoutParams(0, 1, 0.5f));
        for (int band = 0; band < CarAudioParams.EQ_BANDS; ++band) {
            final int b = band;
            mBandSliders[band] = addSlider(row, bandLabel(CarAudioParams.EQ_FREQUENCIES_HZ[band]));
            mBandSliders[band].setOnValueChangeListener((s, value) -> {
                mBands[b] = value;
                mParams.set(CarAudioParams.eqBand(b), value);
                updateCurve();
            });
        }
        mControls = new View[] {mCurve, row, preset, reset};

        mEnabled.setOnCheckedChangeListener((b, checked) -> {
            mParams.set(CarAudioParams.EQ_ENABLED, checked ? 1 : 0);
            updateEnabled();
        });
        reset.setOnClickListener(v -> apply(new int[CarAudioParams.EQ_BANDS], 0));
        preset.setOnClickListener(v -> new AlertDialogBuilder(requireContext())
                .setTitle(R.string.eq_preset_title)
                .setItems(R.array.eq_preset_names, (dialog, which) -> applyPreset(which))
                .show());
    }

    @Override
    public void onResume() {
        super.onResume();
        // The HAL is the source of truth; show its current values.
        mEnabled.setChecked(mParams.get(CarAudioParams.EQ_ENABLED, 0) != 0);
        mPreamp = Math.round(mParams.get(CarAudioParams.EQ_PREAMP, 0));
        mPreampSlider.setValue(mPreamp);
        for (int band = 0; band < CarAudioParams.EQ_BANDS; ++band) {
            mBands[band] = Math.round(mParams.get(CarAudioParams.eqBand(band), 0));
            mBandSliders[band].setValue(mBands[band]);
        }
        updateEnabled();
        updateCurve();
    }

    private EqSliderView addSlider(LinearLayout row, String label) {
        final EqSliderView slider = new EqSliderView(requireContext(), null);
        slider.setLabel(label);
        row.addView(slider, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.MATCH_PARENT, 1));
        return slider;
    }

    private static String bandLabel(float hz) {
        if (hz >= 1000) return Math.round(hz / 1000) + "k";
        return String.valueOf(Math.round(hz));
    }

    private void applyPreset(int index) {
        final String[] gains = getResources().getStringArray(R.array.eq_preset_gains)[index]
                .split(",");
        final int[] bands = new int[CarAudioParams.EQ_BANDS];
        for (int band = 0; band < bands.length; ++band) {
            bands[band] = Integer.parseInt(gains[band].trim());
        }
        apply(bands, 0);
    }

    private void apply(int[] bands, int preamp) {
        mPreamp = preamp;
        mPreampSlider.setValue(preamp);
        mParams.set(CarAudioParams.EQ_PREAMP, preamp);
        for (int band = 0; band < bands.length; ++band) {
            mBands[band] = bands[band];
            mBandSliders[band].setValue(bands[band]);
            mParams.set(CarAudioParams.eqBand(band), bands[band]);
        }
        updateCurve();
    }

    private void updateEnabled() {
        final boolean on = mEnabled.isChecked();
        for (View v : mControls) v.setAlpha(on ? 1f : DISABLED_ALPHA);
        mPreampSlider.setEnabled(on);
        for (EqSliderView s : mBandSliders) s.setEnabled(on);
    }

    private void updateCurve() {
        mResponse.set(mBands, mPreamp);
        mCurve.setResponse(mResponse);
    }
}
