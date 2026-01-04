package com.gschuurman.caraudiotuner;

import android.app.Activity;
import android.car.Car;
import android.car.media.CarAudioManager;
import android.content.ComponentName;
import android.content.ServiceConnection;
import android.os.Bundle;
import android.os.IBinder;
import android.util.Log;

public class BalanceFaderActivity extends Activity {
    private Car mCar;
    private CarAudioManager mCarAudioManager;
    private BalanceFaderView mView;

    // Define the ServiceConnection explicitly
    private final ServiceConnection mServiceConnection = new ServiceConnection() {
        @Override
        public void onServiceConnected(ComponentName name, IBinder service) {
            try {
                if (mCar != null) {
                    mCarAudioManager = (CarAudioManager) mCar.getCarManager(Car.AUDIO_SERVICE);
                }
            } catch (Exception e) {
                Log.e("CarAudioTuner", "Failed to connect to Audio Service", e);
            }
        }

        @Override
        public void onServiceDisconnected(ComponentName name) {
            mCarAudioManager = null;
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_balance_fader);

        mView = findViewById(R.id.bf_view);

        // Connect to Car Service using the ServiceConnection
        mCar = Car.createCar(this, mServiceConnection);
        if (mCar != null) {
            // Note: createCar with ServiceConnection automatically binds, 
            // so explicit connect() is generally not needed in modern Android.
            // If it doesn't connect, uncomment the line below:
            // mCar.connect();
        }

        mView.setListener((balance, fade) -> {
            if (mCarAudioManager != null) {
                try {
                    mCarAudioManager.setBalanceTowardRight(balance);
                    mCarAudioManager.setFadeTowardFront(fade);
                } catch (Exception e) {
                    Log.e("CarAudioTuner", "Failed to set audio settings", e);
                }
            }
        });
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (mCar != null) {
            mCar.disconnect();
            mCar = null;
        }
    }
}