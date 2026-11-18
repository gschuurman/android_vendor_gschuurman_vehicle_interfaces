package com.gschuurman.carstatus;

import android.app.Activity;
import android.car.Car;
import android.car.hardware.CarPropertyConfig;
import android.car.hardware.CarPropertyValue;
import android.car.hardware.property.CarPropertyManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.util.TypedValue;
import android.view.Gravity;
import android.widget.GridLayout;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.util.Locale;

/**
 * Car status dashboard (first version): engine values from the MEMS 1.9 ECU over the K-line, with
 * the coolant temperature as the big tile coloured by the alarm thresholds.
 */
public class MainActivity extends Activity {
    private static final String TAG = "CarStatus";
    private static final float CAUTION_C = 105f, ALARM_C = 110f;

    private final Handler mHandler = new Handler(Looper.getMainLooper());
    private Car mCar;
    private CarPropertyManager mProps;
    private float[] mLive;
    private int mKlineState = -1;
    private long mLiveAt;

    private TextView mCoolant, mLink;
    private TextView mRpm, mBattery, mIntake, mAmbient, mMap, mThrottle, mFans, mFaults;
    private GradientDrawable mCoolantBg;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.HORIZONTAL);
        root.setPadding(dp(24), dp(24), dp(24), dp(24));
        root.setBackgroundColor(0xFF101418);

        LinearLayout left = new LinearLayout(this);
        left.setOrientation(LinearLayout.VERTICAL);
        left.setGravity(Gravity.CENTER);
        mCoolantBg = new GradientDrawable();
        mCoolantBg.setCornerRadius(dp(24));
        mCoolantBg.setColor(0xFF263238);
        left.setBackground(mCoolantBg);
        left.addView(label(getString(R.string.tile_coolant), 22));
        mCoolant = value(96);
        left.addView(mCoolant);
        mLink = label("", 18);
        left.addView(mLink);
        root.addView(left, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.MATCH_PARENT, 1f));

        GridLayout grid = new GridLayout(this);
        grid.setColumnCount(2);
        grid.setPadding(dp(24), 0, 0, 0);
        mRpm = tile(grid, R.string.tile_rpm);
        mBattery = tile(grid, R.string.tile_battery);
        mIntake = tile(grid, R.string.tile_intake);
        mAmbient = tile(grid, R.string.tile_ambient);
        mMap = tile(grid, R.string.tile_map);
        mThrottle = tile(grid, R.string.tile_throttle);
        mFans = tile(grid, R.string.tile_fans);
        mFaults = tile(grid, R.string.tile_faults);
        root.addView(grid, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.MATCH_PARENT, 1.3f));

        setContentView(root);
        render();
        mCar = Car.createCar(this, mHandler, Car.CAR_WAIT_TIMEOUT_DO_NOT_WAIT, (car, ready) -> {
            if (ready) onCarReady(car);
            else mProps = null;
        });
    }

    @Override
    protected void onStart() {
        super.onStart();
        mHandler.post(mStaleCheck);
    }

    @Override
    protected void onStop() {
        mHandler.removeCallbacks(mStaleCheck);
        super.onStop();
    }

    @Override
    protected void onDestroy() {
        if (mProps != null) mProps.unregisterCallback(mCallback);
        if (mCar != null) mCar.disconnect();
        super.onDestroy();
    }

    private final Runnable mStaleCheck = new Runnable() {
        @Override
        public void run() {
            render();
            mHandler.postDelayed(this, 1000);
        }
    };

    private final CarPropertyManager.CarPropertyEventCallback mCallback =
            new CarPropertyManager.CarPropertyEventCallback() {
                @Override
                public void onChangeEvent(CarPropertyValue value) {
                    if (value.getStatus() != CarPropertyValue.STATUS_AVAILABLE) return;
                    if (value.getPropertyId() == Vhal.VENDOR_MEMS_LIVE) {
                        mLive = Vhal.toFloats(value.getValue());
                        mLiveAt = System.currentTimeMillis();
                    } else if (value.getPropertyId() == Vhal.KLINE_STATE) {
                        Object v = value.getValue();
                        if (v instanceof Integer[] && ((Integer[]) v).length > 0) {
                            mKlineState = ((Integer[]) v)[0];
                        }
                    }
                    render();
                }

                @Override
                public void onErrorEvent(int propertyId, int areaId) {}
            };

    private void onCarReady(Car car) {
        mProps = (CarPropertyManager) car.getCarManager(Car.PROPERTY_SERVICE);
        if (mProps == null) return;
        for (int prop : new int[] {Vhal.VENDOR_MEMS_LIVE, Vhal.KLINE_STATE}) {
            CarPropertyConfig<?> c = mProps.getCarPropertyConfig(prop);
            if (c == null) continue;
            try {
                mProps.subscribePropertyEvents(prop, 0f, mCallback);
            } catch (RuntimeException e) {
                Log.w(TAG, "subscribe 0x" + Integer.toHexString(prop), e);
            }
        }
    }

    private void render() {
        boolean fresh = mLive != null && System.currentTimeMillis() - mLiveAt < 3000;
        float[] v = fresh ? mLive : null;
        float c = Vhal.field(v, Vhal.MEMS_COOLANT_C);
        mCoolant.setText(Float.isNaN(c) ? "--" : String.format(Locale.ROOT, "%d°C", Math.round(c)));
        mCoolantBg.setColor(Float.isNaN(c) ? 0xFF263238
                : c >= ALARM_C ? 0xFFB71C1C : c >= CAUTION_C ? 0xFFE65100 : 0xFF1B5E20);
        mLink.setText(linkText());
        mRpm.setText(fmt(Vhal.field(v, Vhal.MEMS_RPM), "%.0f"));
        mBattery.setText(fmt(Vhal.field(v, Vhal.MEMS_BATTERY_V), "%.1f V"));
        mIntake.setText(fmt(Vhal.field(v, Vhal.MEMS_INTAKE_AIR_C), "%.0f°C"));
        mAmbient.setText(fmt(Vhal.field(v, Vhal.MEMS_AMBIENT_C), "%.0f°C"));
        mMap.setText(fmt(Vhal.field(v, Vhal.MEMS_MAP_KPA), "%.0f kPa"));
        mThrottle.setText(fmt(Vhal.field(v, Vhal.MEMS_THROTTLE_DEG), "%.1f°"));
        float f1 = Vhal.field(v, Vhal.MEMS_FAN1), f2 = Vhal.field(v, Vhal.MEMS_FAN2);
        mFans.setText(Float.isNaN(f1) ? "--" : (f1 > 0 ? "1 on" : "1 off") + "  " + (f2 > 0 ? "2 on" : "2 off"));
        float a = Vhal.field(v, Vhal.MEMS_FAULTS_1), b = Vhal.field(v, Vhal.MEMS_FAULTS_2);
        mFaults.setText(Float.isNaN(a) ? "--"
                : (a == 0 && (Float.isNaN(b) || b == 0)) ? getString(R.string.faults_none)
                : String.format(Locale.ROOT, "%02X %02X", (int) a, Float.isNaN(b) ? 0 : (int) b));
    }

    private String linkText() {
        switch (mKlineState) {
            case Vhal.KLINE_ST_CONNECTED: return getString(R.string.link_connected);
            case Vhal.KLINE_ST_WAKING: return getString(R.string.link_waking);
            case Vhal.KLINE_ST_RETRY: return getString(R.string.link_retry);
            case Vhal.KLINE_ST_OFF: return getString(R.string.link_off);
            default: return getString(R.string.link_unknown);
        }
    }

    private static String fmt(float v, String f) {
        return Float.isNaN(v) ? "--" : String.format(Locale.ROOT, f, v);
    }

    private int dp(float v) {
        return Math.round(TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v,
                getResources().getDisplayMetrics()));
    }

    private TextView label(String s, float sp) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextColor(0xB3FFFFFF);
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, sp);
        t.setGravity(Gravity.CENTER);
        return t;
    }

    private TextView value(float sp) {
        TextView t = new TextView(this);
        t.setTextColor(Color.WHITE);
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, sp);
        t.setTypeface(Typeface.DEFAULT_BOLD);
        t.setGravity(Gravity.CENTER);
        return t;
    }

    private TextView tile(GridLayout grid, int labelRes) {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(16), dp(12), dp(16), dp(12));
        GradientDrawable bg = new GradientDrawable();
        bg.setCornerRadius(dp(16));
        bg.setColor(0x1AFFFFFF);
        box.setBackground(bg);
        TextView l = label(getString(labelRes), 16);
        l.setGravity(Gravity.START);
        TextView v = value(32);
        v.setGravity(Gravity.START);
        box.addView(l);
        box.addView(v);
        GridLayout.LayoutParams lp = new GridLayout.LayoutParams(
                GridLayout.spec(GridLayout.UNDEFINED, 1f), GridLayout.spec(GridLayout.UNDEFINED, 1f));
        lp.width = 0;
        lp.height = 0;
        lp.setMargins(dp(6), dp(6), dp(6), dp(6));
        grid.addView(box, lp);
        return v;
    }
}
