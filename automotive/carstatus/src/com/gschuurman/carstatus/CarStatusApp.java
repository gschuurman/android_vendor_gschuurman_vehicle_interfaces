package com.gschuurman.carstatus;

import android.app.Application;
import android.content.Intent;
import android.os.Process;
import android.util.Log;

import com.gschuurman.carstatus.alarm.AlarmService;

/**
 * The app is persistent: the system starts (and restarts) its process in the system user at boot.
 * That process runs the engine alarm. The dashboard activity runs in the driver's user and only
 * reads the VHAL.
 */
public class CarStatusApp extends Application {
    @Override
    public void onCreate() {
        super.onCreate();
        if (Process.myUserHandle().isSystem()) {
            Log.i("CarStatusAlarm", "Persistent process up, starting the alarm service");
            startService(new Intent(this, AlarmService.class));
        }
    }
}
