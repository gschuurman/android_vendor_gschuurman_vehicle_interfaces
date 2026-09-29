package com.gschuurman.caraudiotuner;

import android.os.Bundle;

import androidx.fragment.app.Fragment;
import androidx.fragment.app.FragmentActivity;

import com.android.car.ui.core.CarUi;
import com.android.car.ui.toolbar.NavButtonMode;
import com.android.car.ui.toolbar.ToolbarController;

/**
 * Hosts one car audio settings screen; the screens are entries on the CarSettings "Sound" page
 * (injected settings).
 */
public abstract class CarAudioSettingsActivity extends FragmentActivity {
    abstract int titleRes();

    abstract Fragment createFragment();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_settings);

        final ToolbarController toolbar = CarUi.requireToolbar(this);
        toolbar.setTitle(titleRes());
        toolbar.setNavButtonMode(NavButtonMode.BACK);

        if (savedInstanceState == null) {
            getSupportFragmentManager().beginTransaction()
                    .replace(R.id.settings_container, createFragment())
                    .commit();
        }
    }

    /** Equalizer screen. */
    public static final class Equalizer extends CarAudioSettingsActivity {
        @Override
        int titleRes() {
            return R.string.equalizer_title;
        }

        @Override
        Fragment createFragment() {
            return new EqualizerFragment();
        }
    }

    /** Balance and fader screen. */
    public static final class BalanceFader extends CarAudioSettingsActivity {
        @Override
        int titleRes() {
            return R.string.balance_fader_title;
        }

        @Override
        Fragment createFragment() {
            return new BalanceFaderFragment();
        }
    }
}
