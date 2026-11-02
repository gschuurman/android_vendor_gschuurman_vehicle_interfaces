package com.gschuurman.headunitdebug;

import android.Manifest;
import android.app.Activity;
import android.car.Car;
import android.car.hardware.CarPropertyConfig;
import android.car.hardware.CarPropertyValue;
import android.car.hardware.property.CarPropertyManager;
import android.content.pm.PackageManager;
import android.graphics.drawable.GradientDrawable;
import android.location.GnssStatus;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.util.Log;
import android.util.SparseArray;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.android.car.ui.core.CarUi;
import com.android.car.ui.toolbar.ToolbarController;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * Live status of the peripheral board (MCU values the VHAL publishes, see
 * mcu/protocol/mcu_protocol.h) and the GNSS receiver. Read-only.
 */
public class MainActivity extends Activity {
    private static final String TAG = "HeadUnitDebug";

    // Standard VHAL properties
    private static final int GEAR_SELECTION = 0x11400400;
    private static final int PARKING_BRAKE_ON = 0x11200402;
    private static final int NIGHT_MODE = 0x11200407;
    private static final int IGNITION_STATE = 0x11400409;
    private static final int PERF_VEHICLE_SPEED = 0x11600207;

    // Vendor properties (MCU_PROP_* in mcu_protocol.h, VENDOR_* in SchuurmanVehicleHardware)
    private static final int SCREEN_POWER = 0x21400555;
    private static final int BATTERY_MV = 0x21400600;
    private static final int RAIL_5V_MV = 0x21400601;
    private static final int BOARD_TEMP = 0x21400602;
    private static final int LUX = 0x21400603;
    private static final int AMP_MODE = 0x21400604;
    private static final int AMP_ON = 0x21400605;
    private static final int AUDIO_MUTE = 0x21400606;
    private static final int INPUTS = 0x21400607;
    private static final int STATUS = 0x21400608;
    private static final int POWER_STATE = 0x21400609;
    private static final int OFF_DELAY_S = 0x2140060A;
    private static final int GNSS_FIX = 0x2141060C;
    private static final int MCU_FW_VERSION = 0x2110060D;

    private static final int[] SUBSCRIBED = {
            GEAR_SELECTION, PARKING_BRAKE_ON, NIGHT_MODE, IGNITION_STATE, PERF_VEHICLE_SPEED,
            SCREEN_POWER, BATTERY_MV, RAIL_5V_MV, BOARD_TEMP, LUX, AMP_MODE, AMP_ON, AUDIO_MUTE,
            INPUTS, STATUS, POWER_STATE, OFF_DELAY_S, GNSS_FIX, MCU_FW_VERSION,
    };

    private static final String[] POWER_STATES = {"off", "booting", "running", "shutdown prep",
            "suspended", "waking", "shutting down", "latched off"};

    private enum Dot { NONE, OK, WARN, FAULT, OFF }

    /** One "label   value" line with an optional status dot. */
    private final class Row {
        final TextView value;
        final View dot;

        Row(LinearLayout parent, String label, boolean withDot) {
            LinearLayout line = new LinearLayout(MainActivity.this);
            line.setOrientation(LinearLayout.HORIZONTAL);
            line.setGravity(Gravity.CENTER_VERTICAL);
            line.setPadding(0, dp(3), 0, dp(3));
            if (withDot) {
                dot = new View(MainActivity.this);
                LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(dp(14), dp(14));
                lp.setMarginEnd(dp(10));
                line.addView(dot, lp);
            } else {
                dot = null;
            }
            TextView name = text(label, 18, 0xB3FFFFFF);
            line.addView(name, new LinearLayout.LayoutParams(0, -2, 1f));
            value = text(getString(R.string.no_value), 18, 0xFFFFFFFF);
            value.setGravity(Gravity.END);
            line.addView(value, new LinearLayout.LayoutParams(-2, -2));
            parent.addView(line);
            set(null, Dot.OFF);
        }

        void set(String v, Dot d) {
            value.setText(v == null ? getString(R.string.no_value) : v);
            if (dot == null || d == Dot.NONE) return;
            GradientDrawable g = new GradientDrawable();
            g.setShape(GradientDrawable.OVAL);
            g.setColor(getColor(d == Dot.OK ? R.color.dot_ok
                    : d == Dot.WARN ? R.color.dot_warn
                    : d == Dot.FAULT ? R.color.dot_fault : R.color.dot_off));
            dot.setBackground(g);
        }
    }

    /** A bit of MCU_PROP_INPUTS or MCU_PROP_STATUS. A fault bit lights red when set. */
    private static final class Bit {
        final int mask;
        final boolean fault;
        final Row row;

        Bit(int mask, boolean fault, Row row) {
            this.mask = mask;
            this.fault = fault;
            this.row = row;
        }
    }

    private final Handler mHandler = new Handler(Looper.getMainLooper());
    private final SparseArray<Object> mValues = new SparseArray<>();
    private final List<Bit> mInputBits = new ArrayList<>();
    private final List<Bit> mStatusBits = new ArrayList<>();

    private Car mCar;
    private CarPropertyManager mProps;
    private final List<Integer> mSubscribed = new ArrayList<>();

    private LocationManager mLocation;
    private boolean mGnssRegistered;
    private long mLastFixElapsedMs;
    private Location mLastFix;

    // Board
    private Row mFirmware, mPowerState, mBattery, mRail, mTemp;
    // Android view
    private Row mIgnition, mGear, mParkingBrake, mNight, mSpeed;
    // Display / audio
    private Row mScreen, mLux, mAmpMode, mAmpOn, mMute, mOffDelay;
    // GNSS
    private Row mMcuGnssPower, mMcuNmea, mMcuFix;
    private Row mGpsState, mGpsPosition, mGpsAccuracy, mGpsSpeed, mGpsAge, mGpsSats;
    private SatelliteView mSatView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        ToolbarController toolbar = CarUi.requireToolbar(this);
        toolbar.setTitle(R.string.app_name);

        buildBoardColumn(findViewById(R.id.column_board));
        buildCarColumn(findViewById(R.id.column_car));
        buildGnssColumn(findViewById(R.id.column_gnss));

        mLocation = getSystemService(LocationManager.class);
        mCar = Car.createCar(this, mHandler, Car.CAR_WAIT_TIMEOUT_DO_NOT_WAIT, (car, ready) -> {
            if (ready) onCarReady(car);
            else mProps = null;
        });
    }

    @Override
    protected void onStart() {
        super.onStart();
        ArrayList<String> missing = new ArrayList<>();
        for (String p : new String[] {Manifest.permission.ACCESS_FINE_LOCATION, Car.PERMISSION_SPEED}) {
            if (checkSelfPermission(p) != PackageManager.PERMISSION_GRANTED) missing.add(p);
        }
        if (!missing.isEmpty()) requestPermissions(missing.toArray(new String[0]), 1);
        startGnss();
        mHandler.post(mTicker);
    }

    @Override
    protected void onStop() {
        stopGnss();
        mHandler.removeCallbacks(mTicker);
        super.onStop();
    }

    @Override
    protected void onDestroy() {
        if (mProps != null) mProps.unregisterCallback(mPropCallback);
        if (mCar != null) mCar.disconnect();
        super.onDestroy();
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] results) {
        super.onRequestPermissionsResult(requestCode, permissions, results);
        startGnss();
        if (mCar != null && mCar.isConnected()) onCarReady(mCar);  // CAR_SPEED may be granted now
    }

    // ------------------------------------------------------------------ layout

    private void buildBoardColumn(LinearLayout col) {
        LinearLayout board = section(col, R.string.section_board);
        mFirmware = new Row(board, "Firmware", false);
        mPowerState = new Row(board, "Power state", true);
        mBattery = new Row(board, "Battery (ISO A4)", true);
        mRail = new Row(board, "+5V_SYS rail", true);
        mTemp = new Row(board, "Board temperature", true);

        LinearLayout flags = section(col, R.string.section_flags);
        statusBit(flags, 1 << 0, false, "Phone ports power good");
        statusBit(flags, 1 << 1, true, "Phone port 1 over-current");
        statusBit(flags, 1 << 2, true, "Phone port 2 over-current");
        statusBit(flags, 1 << 3, false, "TPS55288 answering");
        statusBit(flags, 1 << 4, true, "TPS55288 short circuit");
        statusBit(flags, 1 << 5, true, "TPS55288 over-current");
        statusBit(flags, 1 << 6, true, "TPS55288 over-voltage");
        statusBit(flags, 1 << 7, false, "BH1750 answering");
        statusBit(flags, 1 << 10, false, "R72 pull-up (survives MCU reset)");
        statusBit(flags, 1 << 11, true, "Low battery");
        statusBit(flags, 1 << 12, true, "Board hot");
    }

    private void buildCarColumn(LinearLayout col) {
        LinearLayout inputs = section(col, R.string.section_inputs);
        inputBit(inputs, 1 << 0, "ACC (ignition)");
        inputBit(inputs, 1 << 1, "Reverse");
        inputBit(inputs, 1 << 2, "Illumination");
        inputBit(inputs, 1 << 3, "Handbrake wire");
        inputBit(inputs, 1 << 4, "VIM3 3.3 V rail");
        inputBit(inputs, 1 << 5, "Service jumper JP1");
        inputBit(inputs, 1 << 8, "Screen button");
        inputBit(inputs, 1 << 9, "Volume up button");
        inputBit(inputs, 1 << 10, "Volume down button");
        inputBit(inputs, 1 << 11, "Mute button");

        LinearLayout android = section(col, R.string.section_android);
        mIgnition = new Row(android, "Ignition", true);
        mGear = new Row(android, "Gear", true);
        mParkingBrake = new Row(android, "Parking brake", true);
        mNight = new Row(android, "Night mode", true);
        mSpeed = new Row(android, "Speed", false);

        LinearLayout da = section(col, R.string.section_display_audio);
        mScreen = new Row(da, "Backlight", true);
        mLux = new Row(da, "Light sensor", true);
        mAmpMode = new Row(da, "Amp mode", false);
        mAmpOn = new Row(da, "Amp remote output", true);
        mMute = new Row(da, "DAC", true);
        mOffDelay = new Row(da, "Suspend → power off after", false);
    }

    private void buildGnssColumn(LinearLayout col) {
        LinearLayout mcu = section(col, R.string.section_gnss_mcu);
        mMcuGnssPower = new Row(mcu, "GNSS supply", true);
        mMcuNmea = new Row(mcu, "NMEA in last 3 s", true);
        mMcuFix = new Row(mcu, "Fix / satellites", true);

        LinearLayout gps = section(col, R.string.section_gnss_android);
        mGpsState = new Row(gps, "GPS provider", true);
        mGpsPosition = new Row(gps, "Position", false);
        mGpsAccuracy = new Row(gps, "Accuracy", false);
        mGpsSpeed = new Row(gps, "Speed / bearing", false);
        mGpsAge = new Row(gps, "Last fix", true);
        mGpsSats = new Row(gps, "Satellites used / tracked", false);

        LinearLayout sats = section(col, R.string.section_satellites);
        mSatView = new SatelliteView(this);
        sats.addView(mSatView, new LinearLayout.LayoutParams(-1, dp(150)));
    }

    private LinearLayout section(LinearLayout column, int titleRes) {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(16), dp(12), dp(16), dp(12));
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(getColor(R.color.card_background));
        bg.setCornerRadius(dp(12));
        card.setBackground(bg);
        TextView title = text(getString(titleRes), 20, 0xFFFFFFFF);
        title.setPadding(0, 0, 0, dp(6));
        card.addView(title);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, -2);
        lp.topMargin = dp(12);
        column.addView(card, lp);
        return card;
    }

    private void inputBit(LinearLayout parent, int mask, String label) {
        mInputBits.add(new Bit(mask, false, new Row(parent, label, true)));
    }

    private void statusBit(LinearLayout parent, int mask, boolean fault, String label) {
        mStatusBits.add(new Bit(mask, fault, new Row(parent, label, true)));
    }

    private TextView text(String s, int sp, int color) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, sp);
        t.setTextColor(color);
        return t;
    }

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }

    // ------------------------------------------------------------------ VHAL

    private final CarPropertyManager.CarPropertyEventCallback mPropCallback =
            new CarPropertyManager.CarPropertyEventCallback() {
                @Override
                public void onChangeEvent(CarPropertyValue value) {
                    if (value.getStatus() == CarPropertyValue.STATUS_AVAILABLE) {
                        mValues.put(value.getPropertyId(), value.getValue());
                    } else {
                        mValues.remove(value.getPropertyId());
                    }
                    mHandler.post(MainActivity.this::render);
                }

                @Override
                public void onErrorEvent(int propertyId, int areaId) {
                    Log.w(TAG, "Error event for 0x" + Integer.toHexString(propertyId));
                }
            };

    private void onCarReady(Car car) {
        mProps = (CarPropertyManager) car.getCarManager(Car.PROPERTY_SERVICE);
        if (mProps == null) return;
        for (int prop : SUBSCRIBED) {
            if (mSubscribed.contains(prop)) continue;
            CarPropertyConfig<?> config = mProps.getCarPropertyConfig(prop);
            if (config == null) continue;  // not supported, or no permission (yet)
            float rate = config.getChangeMode() == CarPropertyConfig.VEHICLE_PROPERTY_CHANGE_MODE_CONTINUOUS
                    ? 1f : 0f;
            try {
                if (mProps.subscribePropertyEvents(prop, rate, mPropCallback)) mSubscribed.add(prop);
            } catch (RuntimeException e) {
                Log.w(TAG, "Cannot subscribe to 0x" + Integer.toHexString(prop), e);
            }
        }
        Log.i(TAG, "Subscribed to " + mSubscribed.size() + " of " + SUBSCRIBED.length + " properties");
    }

    private Integer intValue(int prop) {
        Object v = mValues.get(prop);
        if (v instanceof Integer) return (Integer) v;
        if (v instanceof Boolean) return ((Boolean) v) ? 1 : 0;
        if (v instanceof Integer[] && ((Integer[]) v).length > 0) return ((Integer[]) v)[0];
        return null;
    }

    private void render() {
        // Board
        Object fw = mValues.get(MCU_FW_VERSION);
        mFirmware.set(fw instanceof String ? (String) fw : "MCU not seen", Dot.NONE);
        Integer ps = intValue(POWER_STATE);
        mPowerState.set(ps == null ? null : ps >= 0 && ps < POWER_STATES.length
                ? POWER_STATES[ps] : String.valueOf(ps), ps == null ? Dot.OFF : ps == 2 ? Dot.OK : Dot.WARN);
        Integer status = intValue(STATUS);
        Integer bat = intValue(BATTERY_MV);
        boolean lowBat = status != null && (status & (1 << 11)) != 0;
        mBattery.set(bat == null || bat < 0 ? null : String.format(Locale.US, "%.2f V", bat / 1000f),
                bat == null ? Dot.OFF : lowBat ? Dot.FAULT : Dot.OK);
        Integer rail = intValue(RAIL_5V_MV);
        mRail.set(rail == null || rail < 0 ? null : String.format(Locale.US, "%.2f V", rail / 1000f),
                rail == null ? Dot.OFF : rail >= 4750 && rail <= 5250 ? Dot.OK : Dot.WARN);
        Integer temp = intValue(BOARD_TEMP);
        boolean hot = status != null && (status & (1 << 12)) != 0;
        boolean tempValid = temp != null && temp != Integer.MIN_VALUE;
        mTemp.set(tempValid ? String.format(Locale.US, "%.1f °C", temp / 10f) : null,
                !tempValid ? Dot.OFF : hot ? Dot.FAULT : Dot.OK);
        for (Bit b : mStatusBits) {
            if (status == null) { b.row.set(null, Dot.OFF); continue; }
            boolean on = (status & b.mask) != 0;
            b.row.set(on ? "yes" : "no", on ? (b.fault ? Dot.FAULT : Dot.OK) : Dot.OFF);
        }

        // Inputs
        Integer inputs = intValue(INPUTS);
        for (Bit b : mInputBits) {
            if (inputs == null) { b.row.set(null, Dot.OFF); continue; }
            boolean on = (inputs & b.mask) != 0;
            b.row.set(on ? "on" : "off", on ? Dot.OK : Dot.OFF);
        }

        // Android view
        Integer ign = intValue(IGNITION_STATE);
        mIgnition.set(ign == null ? null : ignitionName(ign), ign == null ? Dot.OFF : ign >= 3 ? Dot.OK : Dot.OFF);
        Integer gear = intValue(GEAR_SELECTION);
        mGear.set(gear == null ? null : gearName(gear), gear == null ? Dot.OFF : gear == 2 ? Dot.WARN : Dot.OK);
        Integer pb = intValue(PARKING_BRAKE_ON);
        mParkingBrake.set(pb == null ? null : pb != 0 ? "engaged" : "released", pb != null && pb != 0 ? Dot.OK : Dot.OFF);
        Integer night = intValue(NIGHT_MODE);
        mNight.set(night == null ? null : night != 0 ? "night" : "day", night != null && night != 0 ? Dot.OK : Dot.OFF);
        Object speed = mValues.get(PERF_VEHICLE_SPEED);
        mSpeed.set(speed instanceof Float ? String.format(Locale.US, "%.1f km/h", (Float) speed * 3.6f) : null, Dot.NONE);

        // Display and audio
        Integer screen = intValue(SCREEN_POWER);
        mScreen.set(screen == null ? null : screen != 0 ? "on" : "off", screen != null && screen != 0 ? Dot.OK : Dot.OFF);
        Integer lux = intValue(LUX);
        mLux.set(lux == null ? null : lux < 0 ? "no sensor (manual brightness)" : lux + " lux",
                lux != null && lux >= 0 ? Dot.OK : Dot.OFF);
        Integer ampMode = intValue(AMP_MODE);
        mAmpMode.set(ampMode == null ? null : ampMode == 0 ? "off" : ampMode == 1 ? "on" : "auto", Dot.NONE);
        Integer ampOn = intValue(AMP_ON);
        mAmpOn.set(ampOn == null ? null : ampOn != 0 ? "on" : "off", ampOn != null && ampOn != 0 ? Dot.OK : Dot.OFF);
        Integer mute = intValue(AUDIO_MUTE);
        boolean unmuted = status != null && (status & (1 << 13)) != 0;
        mMute.set(status == null ? null : (unmuted ? "playing" : "muted") + (mute != null && mute != 0 ? " (host mute)" : ""),
                status == null ? Dot.OFF : unmuted ? Dot.OK : Dot.WARN);
        Integer offDelay = intValue(OFF_DELAY_S);
        mOffDelay.set(offDelay == null ? null : offDelay == 0 ? "never" : formatDuration(offDelay), Dot.NONE);

        // GNSS from the MCU
        boolean gnssPower = status != null && (status & (1 << 8)) != 0;
        boolean nmea = status != null && (status & (1 << 9)) != 0;
        mMcuGnssPower.set(status == null ? null : gnssPower ? "on" : "off", gnssPower ? Dot.OK : Dot.OFF);
        mMcuNmea.set(status == null ? null : nmea ? "yes" : "no", nmea ? Dot.OK : gnssPower ? Dot.FAULT : Dot.OFF);
        Object fix = mValues.get(GNSS_FIX);
        if (fix instanceof Integer[] && ((Integer[]) fix).length >= 2) {
            Integer[] f = (Integer[]) fix;
            mMcuFix.set((f[0] != 0 ? "fix" : "no fix") + ", " + f[1] + " SV", f[0] != 0 ? Dot.OK : Dot.WARN);
        } else {
            mMcuFix.set(null, Dot.OFF);
        }

        renderGps();
    }

    private static String ignitionName(int v) {
        switch (v) {
            case 1: return "lock";
            case 2: return "off";
            case 3: return "acc";
            case 4: return "on";
            case 5: return "start";
            default: return "undefined";
        }
    }

    private static String gearName(int v) {
        switch (v) {
            case 1: return "neutral";
            case 2: return "reverse";
            case 4: return "park";
            case 8: return "drive";
            default: return "0x" + Integer.toHexString(v);
        }
    }

    private static String formatDuration(int seconds) {
        if (seconds % 3600 == 0) return (seconds / 3600) + " h";
        if (seconds % 60 == 0) return (seconds / 60) + " min";
        return seconds + " s";
    }

    // ------------------------------------------------------------------ GNSS

    private final LocationListener mLocationListener = location -> {
        mLastFix = location;
        mLastFixElapsedMs = SystemClock.elapsedRealtime();
        renderGps();
    };

    private int mSatsUsed, mSatsTracked;

    private final GnssStatus.Callback mGnssCallback = new GnssStatus.Callback() {
        @Override
        public void onSatelliteStatusChanged(GnssStatus status) {
            int used = 0, tracked = 0;
            for (int i = 0; i < status.getSatelliteCount(); i++) {
                if (status.getCn0DbHz(i) > 0) tracked++;
                if (status.usedInFix(i)) used++;
            }
            mSatsUsed = used;
            mSatsTracked = tracked;
            mSatView.setStatus(status);
            renderGps();
        }
    };

    private void startGnss() {
        if (mGnssRegistered || mLocation == null) return;
        if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)
                != PackageManager.PERMISSION_GRANTED) {
            mGpsState.set(getString(R.string.no_permission), Dot.FAULT);
            return;
        }
        try {
            mLocation.requestLocationUpdates(LocationManager.GPS_PROVIDER, 1000, 0,
                    mLocationListener, Looper.getMainLooper());
            mLocation.registerGnssStatusCallback(getMainExecutor(), mGnssCallback);
            mGnssRegistered = true;
        } catch (RuntimeException e) {
            Log.w(TAG, "GPS not available", e);
            mGpsState.set("not available", Dot.FAULT);
        }
    }

    private void stopGnss() {
        if (!mGnssRegistered) return;
        mLocation.removeUpdates(mLocationListener);
        mLocation.unregisterGnssStatusCallback(mGnssCallback);
        mGnssRegistered = false;
    }

    private void renderGps() {
        if (!mGnssRegistered) return;
        boolean enabled = mLocation.isProviderEnabled(LocationManager.GPS_PROVIDER);
        long age = mLastFix == null ? -1 : (SystemClock.elapsedRealtime() - mLastFixElapsedMs) / 1000;
        boolean fresh = mLastFix != null && age < 5;
        mGpsState.set(!enabled ? "disabled" : fresh ? "fix" : "searching",
                !enabled ? Dot.FAULT : fresh ? Dot.OK : Dot.WARN);
        if (mLastFix != null) {
            mGpsPosition.set(String.format(Locale.US, "%.6f, %.6f", mLastFix.getLatitude(),
                    mLastFix.getLongitude()), Dot.NONE);
            String acc = mLastFix.hasAccuracy() ? String.format(Locale.US, "±%.1f m", mLastFix.getAccuracy()) : "?";
            if (mLastFix.hasAltitude()) acc += String.format(Locale.US, ", alt %.0f m", mLastFix.getAltitude());
            mGpsAccuracy.set(acc, Dot.NONE);
            String spd = mLastFix.hasSpeed() ? String.format(Locale.US, "%.1f km/h", mLastFix.getSpeed() * 3.6f) : "?";
            if (mLastFix.hasBearing()) spd += String.format(Locale.US, ", %.0f°", mLastFix.getBearing());
            mGpsSpeed.set(spd, Dot.NONE);
            mGpsAge.set(age + " s ago", fresh ? Dot.OK : Dot.WARN);
        } else {
            mGpsAge.set("none yet", Dot.OFF);
        }
        mGpsSats.set(mSatsUsed + " / " + mSatsTracked, Dot.NONE);
    }

    private final Runnable mTicker = new Runnable() {
        @Override
        public void run() {
            renderGps();  // keeps "last fix" age current
            mHandler.postDelayed(this, 1000);
        }
    };
}
