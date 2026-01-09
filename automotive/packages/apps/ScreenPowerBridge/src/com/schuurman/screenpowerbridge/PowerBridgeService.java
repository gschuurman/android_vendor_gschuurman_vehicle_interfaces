package com.schuurman.screenpowerbridge;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.car.Car;
import android.car.hardware.property.CarPropertyManager;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.os.IBinder;
import android.util.Log;

public class PowerBridgeService extends Service {
    private static final String TAG = "ScreenPowerBridge";
    // This ID matches the VHAL C++ definition below
    private static final int VENDOR_SCREEN_POWER = 0x21400555; 

    private Car mCar;
    private CarPropertyManager mCarPropertyManager;

    private final BroadcastReceiver mScreenReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            String action = intent.getAction();
            if (Intent.ACTION_SCREEN_OFF.equals(action)) {
                // User pressed the button (or timeout) -> Turn OFF GPIO
                setHalProperty(0);
            } else if (Intent.ACTION_SCREEN_ON.equals(action)) {
                // User touched screen/power key -> Turn ON GPIO
                setHalProperty(1);
            }
        }
    };

    @Override
    public void onCreate() {
        super.onCreate();
        // Create persistent notification to keep service alive
        String channelId = "screen_power_bridge";
        NotificationChannel channel = new NotificationChannel(channelId, "Screen Power", NotificationManager.IMPORTANCE_MIN);
        getSystemService(NotificationManager.class).createNotificationChannel(channel);
        startForeground(1, new Notification.Builder(this, channelId).setSmallIcon(android.R.drawable.ic_lock_power_off).build());

        // Connect to Car Service
        mCar = Car.createCar(this, null, Car.CAR_WAIT_TIMEOUT_WAIT_FOREVER, (car, ready) -> {
            if (ready) {
                mCarPropertyManager = (CarPropertyManager) car.getCarManager(Car.PROPERTY_SERVICE);
                Log.i(TAG, "Connected to CarService.");
            }
        });

        // Register for Screen Events
        IntentFilter filter = new IntentFilter();
        filter.addAction(Intent.ACTION_SCREEN_OFF);
        filter.addAction(Intent.ACTION_SCREEN_ON);
        registerReceiver(mScreenReceiver, filter);
    }

    private void setHalProperty(int value) {
        if (mCarPropertyManager != null) {
            try {
                // Write to VHAL: 0 = OFF, 1 = ON
                mCarPropertyManager.setIntProperty(VENDOR_SCREEN_POWER, 0, value);
                Log.d(TAG, "Set VENDOR_SCREEN_POWER to " + value);
            } catch (Exception e) {
                Log.e(TAG, "Failed to set VHAL property", e);
            }
        }
    }

    @Override
    public IBinder onBind(Intent intent) { return null; }
    
    @Override
    public void onDestroy() {
        unregisterReceiver(mScreenReceiver);
        if (mCar != null) mCar.disconnect();
        super.onDestroy();
    }
}