package com.gschuurman.carstatus.alarm;

import android.app.Service;
import android.car.Car;
import android.car.hardware.CarPropertyConfig;
import android.car.hardware.CarPropertyValue;
import android.car.hardware.property.CarPropertyManager;
import android.content.Intent;
import android.media.AudioManager;
import android.media.ToneGenerator;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.SystemClock;
import android.os.SystemProperties;
import android.util.Log;

import com.gschuurman.carstatus.Vhal;
import com.gschuurman.carstatus.alarm.AlarmLogic.Level;
import com.gschuurman.carstatus.alarm.AlarmLogic.Result;

/**
 * Engine alarm, always on: runs in the persistent system-user process (started by CarStatusApp),
 * independent of whether the dashboard is open. Feeds VENDOR_MEMS_LIVE and the ignition state to
 * AlarmLogic and carries out what it decides: overlay, media pause, chime.
 *
 * <p>Bench test (fake engine data for 5 minutes, real data ignored meanwhile):
 * <pre>
 * adb shell setprop debug.carstatus.fake 1
 * adb shell am startservice --user 0 -n com.gschuurman.carstatus/.alarm.AlarmService \
 *     -a com.gschuurman.carstatus.FAKE --ef coolant 112 --ef rpm 2500
 * adb shell am startservice --user 0 -n com.gschuurman.carstatus/.alarm.AlarmService \
 *     -a com.gschuurman.carstatus.FAKE_END
 * </pre>
 */
public class AlarmService extends Service {
    private static final String TAG = "CarStatusAlarm";
    public static final String ACTION_FAKE = "com.gschuurman.carstatus.FAKE";
    public static final String ACTION_FAKE_END = "com.gschuurman.carstatus.FAKE_END";
    private static final long FAKE_MS = 5 * 60_000;
    private static final long TICK_MS = 1000;
    private static final long CHIME_REPEAT_MS = 4000;

    private final Handler mHandler = new Handler(Looper.getMainLooper());
    private Car mCar;
    private CarPropertyManager mProps;
    private AlarmLogic mLogic;
    private AlarmOverlay mOverlay;
    private ToneGenerator mTone;
    private boolean mAcc;
    private long mFakeUntil;
    private float mFakeCoolant = Float.NaN, mFakeRpm;
    private Result mLast;

    @Override
    public void onCreate() {
        super.onCreate();
        mLogic = new AlarmLogic(new AlarmLogic.Config(), this::onAlarm);
        mOverlay = new AlarmOverlay(this, () -> {
            Log.i(TAG, "Acknowledged");
            mLogic.acknowledge(SystemClock.elapsedRealtime());
        });
        mCar = Car.createCar(this, mHandler, Car.CAR_WAIT_TIMEOUT_WAIT_FOREVER, (car, ready) -> {
            if (ready) onCarReady(car);
            else mProps = null;
        });
        mHandler.post(mTick);
        Log.i(TAG, "Alarm service started");
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && fakeAllowed()) {
            if (ACTION_FAKE.equals(intent.getAction())) {
                mFakeUntil = SystemClock.elapsedRealtime() + FAKE_MS;
                mFakeCoolant = intent.getFloatExtra("coolant", 90f);
                mFakeRpm = intent.getFloatExtra("rpm", 2500f);
                Log.w(TAG, "FAKE engine data: coolant " + mFakeCoolant + " rpm " + mFakeRpm);
                feedFake();
            } else if (ACTION_FAKE_END.equals(intent.getAction())) {
                mFakeUntil = 0;
                // Start over: otherwise the fake "running engine" going quiet is DATA_LOST.
                mLogic = new AlarmLogic(new AlarmLogic.Config(), this::onAlarm);
                mLast = null;
                mOverlay.hide();
                Log.w(TAG, "FAKE engine data ended, alarm state reset");
            }
        }
        return START_STICKY;
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public void onDestroy() {
        mHandler.removeCallbacksAndMessages(null);
        mOverlay.hide();
        if (mProps != null) mProps.unregisterCallback(mCallback);
        if (mCar != null) mCar.disconnect();
        if (mTone != null) mTone.release();
        super.onDestroy();
    }

    // Debug builds, or `adb shell setprop debug.carstatus.fake 1` (debug.* is settable by the shell
    // only; this build's ro.debuggable reads 0).
    private static boolean fakeAllowed() {
        return Build.IS_DEBUGGABLE || SystemProperties.getBoolean("debug.carstatus.fake", false);
    }

    private boolean faking() {
        return SystemClock.elapsedRealtime() < mFakeUntil;
    }

    private void feedFake() {
        mLogic.onSample(SystemClock.elapsedRealtime(), mFakeCoolant, mFakeRpm, 0);
    }

    private final Runnable mTick = new Runnable() {
        @Override
        public void run() {
            mHandler.postDelayed(this, TICK_MS);  // first: keeps ticking whatever happens below
            try {
                long now = SystemClock.elapsedRealtime();
                if (faking()) feedFake();
                mLogic.onTick(now, mAcc || faking());
                if (mLast != null && mLast.visible && mLast.level == Level.ALARM
                        && now % CHIME_REPEAT_MS < TICK_MS) {
                    chime(true);
                }
            } catch (Throwable e) {
                Log.e(TAG, "Tick failed", e);
            }
        }
    };

    private final CarPropertyManager.CarPropertyEventCallback mCallback =
            new CarPropertyManager.CarPropertyEventCallback() {
                @Override
                public void onChangeEvent(CarPropertyValue value) {
                    if (value.getStatus() != CarPropertyValue.STATUS_AVAILABLE) return;
                    long now = SystemClock.elapsedRealtime();
                    switch (value.getPropertyId()) {
                        case Vhal.IGNITION_STATE: {
                            int s = (Integer) value.getValue();
                            mAcc = s == Vhal.IGNITION_ON || s == Vhal.IGNITION_START;
                            mLogic.onTick(now, mAcc || faking());
                            break;
                        }
                        case Vhal.VENDOR_MEMS_LIVE: {
                            if (faking()) break;
                            float[] v = Vhal.toFloats(value.getValue());
                            float faults = Vhal.field(v, Vhal.MEMS_FAULTS_1);
                            mLogic.onSample(now, Vhal.field(v, Vhal.MEMS_COOLANT_C),
                                    Vhal.field(v, Vhal.MEMS_RPM),
                                    Float.isNaN(faults) ? 0 : (int) faults);
                            break;
                        }
                        default:
                            break;
                    }
                }

                @Override
                public void onErrorEvent(int propertyId, int areaId) {
                    Log.w(TAG, "Error event 0x" + Integer.toHexString(propertyId));
                }
            };

    private void onCarReady(Car car) {
        mProps = (CarPropertyManager) car.getCarManager(Car.PROPERTY_SERVICE);
        if (mProps == null) return;
        for (int prop : new int[] {Vhal.IGNITION_STATE, Vhal.VENDOR_MEMS_LIVE}) {
            CarPropertyConfig<?> config = mProps.getCarPropertyConfig(prop);
            if (config == null) {
                Log.w(TAG, "Property 0x" + Integer.toHexString(prop) + " not available");
                continue;
            }
            try {
                mProps.subscribePropertyEvents(prop, 0f, mCallback);
            } catch (RuntimeException e) {
                Log.e(TAG, "Cannot subscribe to 0x" + Integer.toHexString(prop), e);
            }
        }
    }

    // Each action on its own: one failing (permissions, audio, window manager) must never stop
    // the others or take the process down. The overlay goes first.
    private void onAlarm(Result r) {
        Log.w(TAG, "Alarm " + r);
        Result prev = mLast;
        mLast = r;
        try {
            mOverlay.update(r);
        } catch (Throwable e) {
            Log.e(TAG, "Overlay failed", e);
        }
        if (r.pauseMedia) {
            try {
                int n = MediaPauser.pauseAll(this);
                Log.w(TAG, "Paused " + n + " media session(s)");
            } catch (Throwable e) {
                Log.e(TAG, "Media pause failed", e);
            }
        }
        boolean newlyShown = r.visible && (prev == null || !prev.visible || prev.level != r.level);
        if (newlyShown) chime(r.level == Level.ALARM);
    }

    private void chime(boolean alarm) {
        try {
            if (mTone == null) {
                mTone = new ToneGenerator(AudioManager.STREAM_ALARM, ToneGenerator.MAX_VOLUME);
            }
            mTone.startTone(alarm ? ToneGenerator.TONE_CDMA_EMERGENCY_RINGBACK
                                  : ToneGenerator.TONE_PROP_BEEP2, alarm ? 1500 : 400);
        } catch (Throwable e) {
            Log.w(TAG, "Chime failed", e);
        }
    }
}
