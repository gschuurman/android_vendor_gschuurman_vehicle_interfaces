package com.schuurman.vim3.screenoff;

import android.app.Activity;
import android.os.Bundle;
import android.os.PowerManager;
import android.os.SystemClock;

public class ScreenOffActivity extends Activity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        PowerManager pm = (PowerManager) getSystemService(POWER_SERVICE);
        if (pm != null) {
            pm.goToSleep(SystemClock.uptimeMillis());
        }
        finish();
    }
}
