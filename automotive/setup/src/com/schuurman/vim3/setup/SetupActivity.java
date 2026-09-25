package com.schuurman.vim3.setup;

import android.Manifest;
import android.app.Activity;
import android.app.AlarmManager;
import android.app.DatePickerDialog;
import android.app.TimePickerDialog;
import android.app.UiModeManager;
import android.app.admin.DevicePolicyManager;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothManager;
import android.content.ActivityNotFoundException;
import android.content.BroadcastReceiver;
import android.content.ComponentName;
import android.content.ContentResolver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Insets;
import android.location.LocationManager;
import android.net.NetworkInfo;
import android.net.wifi.ScanResult;
import android.net.wifi.WifiConfiguration;
import android.net.wifi.WifiInfo;
import android.net.wifi.WifiManager;
import android.os.Bundle;
import android.os.Process;
import android.provider.Settings;
import android.text.InputType;
import android.util.Log;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.WindowInsets;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.Toast;

import com.android.internal.app.LocalePicker;

import java.text.DateFormat;
import java.util.ArrayList;
import java.util.Calendar;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.TimeZone;

/**
 * First-boot setup wizard, modelled on LineageOS's SetupWizard (packages/apps/SetupWizard) minus the
 * phone-only pages (SIM, biometrics, gestures, recovery update): language + accessibility, Wi-Fi,
 * date & time, Bluetooth phone pairing, location, driver name, a few preferences, an optional screen
 * lock, then a Google account, then "finish", which marks the device and current user as provisioned,
 * disables this HOME activity and hands over to the real launcher. Any step can be skipped and
 * redone later from Settings.
 *
 * Runs while the driver user is still locked (see directBootAware on the manifest entry), so any
 * state gathered here (name, unit/theme preferences, ...) is written to device-protected storage
 * (createDeviceProtectedStorageContext), never to normal credential-encrypted SharedPreferences;
 * other components can read the same "vim3_setup" file the same way once this device ships more
 * than the setup wizard itself.
 */
public class SetupActivity extends Activity {
    private static final String TAG = "Vim3Setup";
    private static final String USER_SETUP_COMPLETE = "user_setup_complete";
    private static final String GOOGLE_ACCOUNT_TYPE = "com.google";

    private static final String PREFS_FILE = "vim3_setup";
    private static final String PREF_DRIVER_NAME = "driver_name";
    private static final String PREF_UNITS_METRIC = "units_metric";
    private static final String PREF_DARK_THEME = "dark_theme";

    private static final int REQUEST_BT_PERMISSIONS = 1;
    private static final int REQUEST_ENABLE_BT = 2;
    private static final int REQUEST_WIFI_PERMISSIONS = 3;

    private static final String STATE_STEP = "step";

    private interface StepContent {
        View build(Step step);
    }

    /** One page of the wizard. {@link #onNext} runs only when the user taps Next (not Skip). */
    private static final class Step {
        final String title;
        final String subtitle;
        final boolean skippable;
        final StepContent content;
        Runnable onNext;
        // Rebuild when coming back to the wizard (the step shows state another activity can change).
        boolean refreshOnResume;

        Step(String title, String subtitle, boolean skippable, StepContent content) {
            this.title = title;
            this.subtitle = subtitle;
            this.skippable = skippable;
            this.content = content;
        }
    }

    private final List<Step> steps = new ArrayList<>();
    private int stepIndex;

    private TextView stepLabel;
    private TextView titleView;
    private TextView subtitleView;
    private FrameLayout contentFrame;
    private Button backButton;
    private Button skipButton;
    private Button nextButton;

    // Bluetooth pairing state; the views are non-null only while the Bluetooth step is showing.
    private BluetoothAdapter bluetoothAdapter;
    private TextView btStatus;
    private LinearLayout btDeviceList;
    private final Set<String> btDiscoveredAddresses = new LinkedHashSet<>();
    private boolean btReceiverRegistered;

    private final BroadcastReceiver btReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            final String action = intent.getAction();
            if (BluetoothDevice.ACTION_FOUND.equals(action)) {
                onDeviceFound(intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE));
            } else if (BluetoothDevice.ACTION_BOND_STATE_CHANGED.equals(action)) {
                onBondStateChanged(intent);
            } else if (BluetoothAdapter.ACTION_DISCOVERY_FINISHED.equals(action) && btStatus != null) {
                btStatus.setText("Scan finished. Tap a device to pair, or scan again.");
            }
        }
    };

    // Wi-Fi pairing state; the views are non-null only while the Wi-Fi step is showing.
    private WifiManager wifiManager;
    private TextView wifiStatus;
    private LinearLayout wifiNetworkList;
    private List<ScanResult> lastWifiResults = Collections.emptyList();
    private boolean wifiReceiverRegistered;

    private final BroadcastReceiver wifiReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            final String action = intent.getAction();
            if (WifiManager.SCAN_RESULTS_AVAILABLE_ACTION.equals(action)) {
                onWifiScanResults();
            } else if (WifiManager.NETWORK_STATE_CHANGED_ACTION.equals(action) && wifiStatus != null) {
                onWifiNetworkStateChanged(intent);
            }
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (isProvisioned()) {
            // Already set up (e.g. an upgrade over an existing device): stay out of the way.
            complete();
            return;
        }
        final BluetoothManager bm = getSystemService(BluetoothManager.class);
        bluetoothAdapter = bm != null ? bm.getAdapter() : null;
        wifiManager = getSystemService(WifiManager.class);

        buildSteps();
        setContentView(buildWizardUi());
        // A language or theme change recreates the activity: pick up where the user was.
        showStep(savedInstanceState != null
                ? Math.min(savedInstanceState.getInt(STATE_STEP, 0), steps.size() - 1) : 0);
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        outState.putInt(STATE_STEP, stepIndex);
    }

    @Override
    public void onBackPressed() {
        // This is the home screen while unprovisioned; Back moves within the wizard, not out of it.
        goBack();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (titleView != null && steps.get(stepIndex).refreshOnResume) {
            showStep(stepIndex);
        }
        if (bluetoothAdapter != null && !btReceiverRegistered) {
            final IntentFilter filter = new IntentFilter();
            filter.addAction(BluetoothDevice.ACTION_FOUND);
            filter.addAction(BluetoothDevice.ACTION_BOND_STATE_CHANGED);
            filter.addAction(BluetoothAdapter.ACTION_DISCOVERY_FINISHED);
            registerReceiver(btReceiver, filter);
            btReceiverRegistered = true;
        }
        if (wifiManager != null && !wifiReceiverRegistered) {
            final IntentFilter filter = new IntentFilter();
            filter.addAction(WifiManager.SCAN_RESULTS_AVAILABLE_ACTION);
            filter.addAction(WifiManager.NETWORK_STATE_CHANGED_ACTION);
            registerReceiver(wifiReceiver, filter);
            wifiReceiverRegistered = true;
        }
    }

    @Override
    protected void onPause() {
        super.onPause();
        if (btReceiverRegistered) {
            unregisterReceiver(btReceiver);
            btReceiverRegistered = false;
        }
        if (wifiReceiverRegistered) {
            unregisterReceiver(wifiReceiver);
            wifiReceiverRegistered = false;
        }
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (bluetoothAdapter != null && hasBluetoothPermissions()) {
            try {
                if (bluetoothAdapter.isDiscovering()) {
                    bluetoothAdapter.cancelDiscovery();
                }
            } catch (SecurityException ignored) {
                // Permission was revoked between the check and the call; nothing to clean up.
            }
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQUEST_BT_PERMISSIONS || requestCode == REQUEST_WIFI_PERMISSIONS) {
            showStep(stepIndex); // rebuild the current step so it reflects the new grant state
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQUEST_ENABLE_BT) {
            showStep(stepIndex); // rebuild so "Turn on Bluetooth" reflects the new adapter state
        }
    }

    private boolean isProvisioned() {
        final ContentResolver cr = getContentResolver();
        return Settings.Global.getInt(cr, Settings.Global.DEVICE_PROVISIONED, 0) == 1
                && Settings.Secure.getInt(cr, USER_SETUP_COMPLETE, 0) == 1;
    }

    private SharedPreferences devicePrefs() {
        return createDeviceProtectedStorageContext().getSharedPreferences(PREFS_FILE, MODE_PRIVATE);
    }

    // ---- Wizard steps ----------------------------------------------------------------------

    private void buildSteps() {
        steps.add(new Step("Set up your head unit",
                "This will only take a few minutes. You can skip any step and finish it later "
                        + "from Settings.",
                false,
                this::buildWelcomeStep));

        steps.add(new Step("Connect to Wi-Fi",
                "Wi-Fi gets you software updates and lets Google apps sign in.",
                true,
                this::buildWifiStep));

        final Step dateTime = new Step("Date & time",
                "With automatic time on, the clock is set from the network once Wi-Fi is up.",
                true,
                this::buildDateTimeStep);
        dateTime.refreshOnResume = true;
        steps.add(dateTime);

        steps.add(new Step("Pair your phone",
                "Pair a phone over Bluetooth for calls, media and Android Auto.",
                true,
                this::buildBluetoothStep));

        steps.add(new Step("Location",
                "Used by navigation, weather and finding nearby places.",
                true,
                this::buildLocationStep));

        steps.add(new Step("Personal information",
                "What should the head unit call you?",
                true,
                this::buildPersonalInfoStep));

        steps.add(new Step("Preferences",
                "A few defaults you can always change later in Settings.",
                true,
                this::buildPreferencesStep));

        final Step screenLock = new Step("Protect your head unit",
                "Optional: require a PIN, pattern or password to unlock your profile. It is "
                        + "checked in the secure hardware (TEE).",
                true,
                this::buildScreenLockStep);
        screenLock.refreshOnResume = true;
        steps.add(screenLock);

        steps.add(new Step("Add a Google account",
                "Needed for the Play Store and Android Auto.",
                true,
                step -> singleButtonStep("Add a Google account",
                        v -> open(new Intent(Settings.ACTION_ADD_ACCOUNT)
                                .putExtra(Settings.EXTRA_ACCOUNT_TYPES,
                                        new String[] {GOOGLE_ACCOUNT_TYPE})))));

        steps.add(new Step("All set",
                "Tap Finish setup to start using your head unit.",
                false,
                step -> text("You can change any of this later from Settings.", 22)));
    }

    private View buildPersonalInfoStep(Step step) {
        final LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER_HORIZONTAL);

        final EditText input = new EditText(this);
        input.setHint("Your name");
        input.setTextSize(TypedValue.COMPLEX_UNIT_SP, 26);
        input.setText(devicePrefs().getString(PREF_DRIVER_NAME, ""));
        final LinearLayout.LayoutParams lp =
                new LinearLayout.LayoutParams(dp(480), LinearLayout.LayoutParams.WRAP_CONTENT);
        input.setLayoutParams(lp);
        root.addView(input);

        step.onNext = () -> {
            final String name = input.getText().toString().trim();
            if (!name.isEmpty()) {
                devicePrefs().edit().putString(PREF_DRIVER_NAME, name).apply();
            }
        };
        return root;
    }

    private View buildPreferencesStep(Step step) {
        final SharedPreferences prefs = devicePrefs();
        final LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER_HORIZONTAL);

        final Switch unitsSwitch = new Switch(this);
        unitsSwitch.setText("Use metric units (km, °C)");
        unitsSwitch.setTextSize(TypedValue.COMPLEX_UNIT_SP, 22);
        unitsSwitch.setChecked(prefs.getBoolean(PREF_UNITS_METRIC, true));
        unitsSwitch.setPadding(0, dp(12), 0, dp(12));
        root.addView(unitsSwitch);

        final Switch darkSwitch = new Switch(this);
        darkSwitch.setText("Dark theme");
        darkSwitch.setTextSize(TypedValue.COMPLEX_UNIT_SP, 22);
        darkSwitch.setChecked(prefs.getBoolean(PREF_DARK_THEME, false));
        darkSwitch.setPadding(0, dp(12), 0, dp(12));
        root.addView(darkSwitch);

        step.onNext = () -> {
            prefs.edit()
                    .putBoolean(PREF_UNITS_METRIC, unitsSwitch.isChecked())
                    .putBoolean(PREF_DARK_THEME, darkSwitch.isChecked())
                    .apply();
            applyDarkTheme(darkSwitch.isChecked());
        };
        return root;
    }

    private void applyDarkTheme(boolean dark) {
        final UiModeManager uiModeManager = getSystemService(UiModeManager.class);
        if (uiModeManager == null) {
            return;
        }
        try {
            uiModeManager.setNightMode(
                    dark ? UiModeManager.MODE_NIGHT_YES : UiModeManager.MODE_NIGHT_NO);
        } catch (SecurityException e) {
            Log.w(TAG, "cannot set night mode", e);
        }
    }

    // ---- Welcome: language + accessibility (LineageOS WelcomeActivity/LocaleActivity) ------------

    private View buildWelcomeStep(Step step) {
        final LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER_HORIZONTAL);

        root.addView(text("Language", 20));
        final List<LocalePicker.LocaleInfo> locales = LocalePicker.getAllAssetLocales(this, false);
        final Locale current = Locale.getDefault();
        int selected = 0;
        for (int i = 0; i < locales.size(); i++) {
            if (locales.get(i).getLocale().equals(current)) {
                selected = i;
            }
        }
        final Spinner picker = spinner(locales, selected);
        picker.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(AdapterView<?> parent, View view, int position, long id) {
                final Locale locale = locales.get(position).getLocale();
                if (!locale.equals(Locale.getDefault())) {
                    // System-wide; recreates this activity, which comes back on this step.
                    LocalePicker.updateLocale(locale);
                }
            }

            @Override
            public void onNothingSelected(AdapterView<?> parent) {
            }
        });
        root.addView(picker);

        root.addView(button("Accessibility",
                v -> open(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))));
        return root;
    }

    // ---- Date & time (LineageOS DateTimeActivity) ------------------------------------------------

    private View buildDateTimeStep(Step step) {
        final ContentResolver cr = getContentResolver();
        final LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER_HORIZONTAL);

        final TextView now = text(DateFormat.getDateTimeInstance(DateFormat.MEDIUM, DateFormat.SHORT)
                .format(Calendar.getInstance().getTime()), 22);
        root.addView(now);

        final Switch autoTime = new Switch(this);
        autoTime.setText("Set time automatically");
        autoTime.setTextSize(TypedValue.COMPLEX_UNIT_SP, 22);
        autoTime.setChecked(Settings.Global.getInt(cr, Settings.Global.AUTO_TIME, 1) != 0);
        autoTime.setPadding(0, dp(12), 0, dp(12));
        root.addView(autoTime);

        // Time zones of the current locale's country first, then all of them.
        final List<String> zones = new ArrayList<>();
        final String country = Locale.getDefault().getCountry();
        if (!country.isEmpty()) {
            Collections.addAll(zones, android.icu.util.TimeZone.getAvailableIDs(country));
        }
        for (String id : TimeZone.getAvailableIDs()) {
            if (id.contains("/") && !id.startsWith("Etc/") && !id.startsWith("SystemV/")
                    && !zones.contains(id)) {
                zones.add(id);
            }
        }
        final String currentZone = TimeZone.getDefault().getID();
        if (!zones.contains(currentZone)) {
            zones.add(0, currentZone);
        }
        final List<String> labels = new ArrayList<>();
        for (String id : zones) {
            labels.add(zoneLabel(id));
        }
        root.addView(text("Time zone", 20));
        final Spinner zonePicker = spinner(labels, zones.indexOf(currentZone));
        zonePicker.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(AdapterView<?> parent, View view, int position, long id) {
                final String zone = zones.get(position);
                if (!zone.equals(TimeZone.getDefault().getID())) {
                    getSystemService(AlarmManager.class).setTimeZone(zone);
                    now.setText(DateFormat.getDateTimeInstance(DateFormat.MEDIUM, DateFormat.SHORT)
                            .format(Calendar.getInstance(TimeZone.getTimeZone(zone)).getTime()));
                }
            }

            @Override
            public void onNothingSelected(AdapterView<?> parent) {
            }
        });
        root.addView(zonePicker);

        final LinearLayout manual = new LinearLayout(this);
        manual.setOrientation(LinearLayout.HORIZONTAL);
        manual.setGravity(Gravity.CENTER_HORIZONTAL); // CENTER + the buttons' top margin clips them
        final Button setDate = button("Set date", v -> {
            final Calendar c = Calendar.getInstance();
            new DatePickerDialog(this, (picker, y, m, d) -> {
                final Calendar t = Calendar.getInstance();
                t.set(y, m, d);
                setSystemTime(t.getTimeInMillis());
            }, c.get(Calendar.YEAR), c.get(Calendar.MONTH), c.get(Calendar.DAY_OF_MONTH)).show();
        });
        final Button setTime = button("Set time", v -> {
            final Calendar c = Calendar.getInstance();
            new TimePickerDialog(this, (picker, h, min) -> {
                final Calendar t = Calendar.getInstance();
                t.set(Calendar.HOUR_OF_DAY, h);
                t.set(Calendar.MINUTE, min);
                t.set(Calendar.SECOND, 0);
                setSystemTime(t.getTimeInMillis());
            }, c.get(Calendar.HOUR_OF_DAY), c.get(Calendar.MINUTE),
                    android.text.format.DateFormat.is24HourFormat(this)).show();
        });
        manual.addView(setDate);
        manual.addView(setTime);
        root.addView(manual);

        final Runnable updateManual = () -> {
            setDate.setEnabled(!autoTime.isChecked());
            setTime.setEnabled(!autoTime.isChecked());
        };
        updateManual.run();
        autoTime.setOnCheckedChangeListener((b, checked) -> {
            Settings.Global.putInt(cr, Settings.Global.AUTO_TIME, checked ? 1 : 0);
            updateManual.run();
        });
        return wrapScroll(root);
    }

    private String zoneLabel(String id) {
        final TimeZone tz = TimeZone.getTimeZone(id);
        final int offsetMin = tz.getOffset(System.currentTimeMillis()) / 60000;
        final String city = id.substring(id.lastIndexOf('/') + 1).replace('_', ' ');
        return String.format(Locale.ROOT, "%s (GMT%s%02d:%02d)", city, offsetMin < 0 ? "-" : "+",
                Math.abs(offsetMin) / 60, Math.abs(offsetMin) % 60);
    }

    private void setSystemTime(long millis) {
        try {
            getSystemService(AlarmManager.class).setTime(millis);
        } catch (SecurityException e) {
            Log.w(TAG, "cannot set time", e);
        }
        showStep(stepIndex);
    }

    // ---- Location (LineageOS LocationSettingsActivity) --------------------------------------------

    private View buildLocationStep(Step step) {
        final LocationManager lm = getSystemService(LocationManager.class);
        final LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER_HORIZONTAL);

        final Switch location = new Switch(this);
        location.setText("Use location");
        location.setTextSize(TypedValue.COMPLEX_UNIT_SP, 22);
        location.setChecked(lm != null && lm.isLocationEnabled());
        location.setPadding(0, dp(12), 0, dp(12));
        root.addView(location);

        final Switch assisted = new Switch(this);
        assisted.setText("Faster GPS fix using network data (assisted GPS)");
        assisted.setTextSize(TypedValue.COMPLEX_UNIT_SP, 22);
        assisted.setChecked(Settings.Global.getInt(getContentResolver(),
                Settings.Global.ASSISTED_GPS_ENABLED, 1) != 0);
        assisted.setPadding(0, dp(12), 0, dp(12));
        root.addView(assisted);

        step.onNext = () -> {
            if (lm != null) {
                lm.setLocationEnabledForUser(location.isChecked(), Process.myUserHandle());
            }
            Settings.Global.putInt(getContentResolver(), Settings.Global.ASSISTED_GPS_ENABLED,
                    assisted.isChecked() ? 1 : 0);
        };
        return root;
    }

    // ---- Screen lock (LineageOS ScreenLockActivity) -----------------------------------------------

    private View buildScreenLockStep(Step step) {
        final boolean secure = getSystemService(android.app.KeyguardManager.class).isDeviceSecure();
        final LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER_HORIZONTAL);
        root.addView(text(secure ? "A screen lock is set." : "No screen lock is set.", 22));
        // CarSettings' SettingsScreenLockActivity handles this (PIN, pattern or password).
        root.addView(button(secure ? "Change screen lock" : "Set screen lock",
                v -> open(new Intent(DevicePolicyManager.ACTION_SET_NEW_PASSWORD))));
        return root;
    }

    // ---- Wi-Fi ---------------------------------------------------------------------------------

    private View buildWifiStep(Step step) {
        final LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER_HORIZONTAL);

        if (wifiManager == null) {
            root.addView(text("Wi-Fi is not available on this device.", 22));
            return root;
        }

        wifiStatus = text("", 20);
        root.addView(wifiStatus);

        final ScrollView scroll = new ScrollView(this);
        wifiNetworkList = new LinearLayout(this);
        wifiNetworkList.setOrientation(LinearLayout.VERTICAL);
        wifiNetworkList.setGravity(Gravity.CENTER_HORIZONTAL);
        scroll.addView(wifiNetworkList);
        scroll.setLayoutParams(new LinearLayout.LayoutParams(dp(640), dp(320)));
        root.addView(scroll);

        // Hidden and enterprise (802.1x) networks aren't modeled by this inline flow; always
        // leave the full Settings picker reachable as a fallback.
        root.addView(button("Open Wi-Fi settings", v ->
                open(new Intent(Settings.ACTION_WIFI_SETTINGS))));

        if (!hasWifiPermissions()) {
            wifiStatus.setText("Wi-Fi permission is needed to scan for networks.");
            root.addView(button("Grant Wi-Fi permission", v ->
                    requestPermissions(new String[] {Manifest.permission.NEARBY_WIFI_DEVICES},
                            REQUEST_WIFI_PERMISSIONS)));
            return root;
        }

        if (!wifiManager.isWifiEnabled()) {
            wifiStatus.setText("Turn on Wi-Fi to scan for networks.");
            root.addView(button("Turn on Wi-Fi", v -> {
                wifiManager.setWifiEnabled(true);
                showStep(stepIndex);
            }));
            return root;
        }

        renderWifiResults(lastWifiResults);
        root.addView(button("Scan for networks", v -> startWifiScan()));
        wifiStatus.setText(lastWifiResults.isEmpty() ? "Ready to scan." : "Tap a network to join.");
        return root;
    }

    private boolean hasWifiPermissions() {
        return checkSelfPermission(Manifest.permission.NEARBY_WIFI_DEVICES)
                == PackageManager.PERMISSION_GRANTED;
    }

    private void startWifiScan() {
        if (!hasWifiPermissions() || wifiNetworkList == null) {
            return;
        }
        wifiNetworkList.removeAllViews();
        wifiStatus.setText("Scanning…");
        try {
            wifiManager.startScan();
        } catch (SecurityException e) {
            Log.w(TAG, "cannot start Wi-Fi scan", e);
        }
    }

    private void onWifiScanResults() {
        if (!hasWifiPermissions()) {
            return;
        }
        // Keep only the strongest result per SSID, ordered by signal strength.
        final Map<String, ScanResult> strongest = new LinkedHashMap<>();
        try {
            for (ScanResult result : wifiManager.getScanResults()) {
                if (result.SSID == null || result.SSID.isEmpty()) {
                    continue;
                }
                final ScanResult existing = strongest.get(result.SSID);
                if (existing == null || result.level > existing.level) {
                    strongest.put(result.SSID, result);
                }
            }
        } catch (SecurityException e) {
            Log.w(TAG, "cannot read Wi-Fi scan results", e);
            return;
        }
        final List<ScanResult> results = new ArrayList<>(strongest.values());
        results.sort((a, b) -> b.level - a.level);
        lastWifiResults = results;
        if (wifiNetworkList != null) {
            renderWifiResults(results);
            if (wifiStatus != null) {
                wifiStatus.setText(results.isEmpty()
                        ? "No networks found. Try scanning again."
                        : "Tap a network to join.");
            }
        }
    }

    private void renderWifiResults(List<ScanResult> results) {
        wifiNetworkList.removeAllViews();
        for (ScanResult result : results) {
            final String security = wifiSecurityLabel(result.capabilities);
            final String label = result.SSID + (security.isEmpty() ? "" : "  (" + security + ")");
            wifiNetworkList.addView(button(label, v -> onWifiNetworkTapped(result)));
        }
    }

    private String wifiSecurityLabel(String capabilities) {
        if (capabilities == null) {
            return "";
        }
        if (capabilities.contains("WEP")) {
            return "WEP";
        }
        if (capabilities.contains("SAE")) {
            return "WPA3";
        }
        if (capabilities.contains("PSK") || capabilities.contains("WPA")) {
            return "WPA/WPA2";
        }
        return "Open";
    }

    private void onWifiNetworkTapped(ScanResult result) {
        final String security = wifiSecurityLabel(result.capabilities);
        if ("WEP".equals(security)) {
            Toast.makeText(this, "WEP networks aren't supported here — use Wi-Fi settings.",
                    Toast.LENGTH_LONG).show();
            return;
        }
        if ("Open".equals(security)) {
            connectToWifi(result.SSID, null, false, true);
            return;
        }
        renderWifiPasswordPrompt(result.SSID, "WPA3".equals(security));
    }

    private void renderWifiPasswordPrompt(String ssid, boolean isWpa3) {
        wifiNetworkList.removeAllViews();
        wifiNetworkList.addView(text("Password for " + ssid, 20));

        final EditText password = new EditText(this);
        password.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        password.setLayoutParams(new LinearLayout.LayoutParams(dp(480),
                LinearLayout.LayoutParams.WRAP_CONTENT));
        wifiNetworkList.addView(password);

        final LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_HORIZONTAL); // CENTER + the buttons' top margin clips them
        row.addView(button("Cancel", v -> renderWifiResults(lastWifiResults)));
        row.addView(button("Connect", v ->
                connectToWifi(ssid, password.getText().toString(), isWpa3, false)));
        wifiNetworkList.addView(row);
    }

    private void connectToWifi(String ssid, String passphrase, boolean isWpa3, boolean isOpen) {
        final WifiConfiguration config = new WifiConfiguration();
        config.SSID = quoted(ssid);
        if (isOpen) {
            config.allowedKeyManagement.set(WifiConfiguration.KeyMgmt.NONE);
        } else if (isWpa3) {
            config.allowedKeyManagement.set(WifiConfiguration.KeyMgmt.SAE);
            config.preSharedKey = quoted(passphrase);
        } else {
            config.allowedKeyManagement.set(WifiConfiguration.KeyMgmt.WPA2_PSK);
            config.preSharedKey = quoted(passphrase);
        }
        if (wifiStatus != null) {
            wifiStatus.setText("Connecting to " + ssid + "…");
        }
        // NETWORK_SETTINGS (platform-signed, auto-granted) lets a real setup wizard connect
        // directly and deterministically, rather than dropping an app-scoped suggestion and
        // waiting for the system to decide whether/when to use it.
        wifiManager.connect(config, new WifiManager.ActionListener() {
            @Override
            public void onSuccess() {
                // Final confirmation comes from the NETWORK_STATE_CHANGED_ACTION receiver once
                // the connection actually comes up (a wrong password fails after this point).
            }

            @Override
            public void onFailure(int reason) {
                if (wifiStatus != null) {
                    wifiStatus.setText("Couldn't connect to " + ssid
                            + " — try Wi-Fi settings instead.");
                }
            }
        });
        renderWifiResults(lastWifiResults);
    }

    private void onWifiNetworkStateChanged(Intent intent) {
        final NetworkInfo info = intent.getParcelableExtra(WifiManager.EXTRA_NETWORK_INFO);
        if (info == null || !info.isConnected()) {
            return;
        }
        final WifiInfo current = wifiManager.getConnectionInfo();
        final String ssid = current != null ? unquoted(current.getSSID()) : null;
        wifiStatus.setText(ssid != null ? "Connected to " + ssid + "." : "Connected to Wi-Fi.");
    }

    private String quoted(String s) {
        return "\"" + s + "\"";
    }

    private String unquoted(String s) {
        return s != null && s.length() >= 2 && s.startsWith("\"") && s.endsWith("\"")
                ? s.substring(1, s.length() - 1) : s;
    }

    // ---- Bluetooth pairing -------------------------------------------------------------------

    private View buildBluetoothStep(Step step) {
        final LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER_HORIZONTAL);

        if (bluetoothAdapter == null) {
            root.addView(text("Bluetooth is not available on this device.", 22));
            return root;
        }

        btStatus = text("", 20);
        root.addView(btStatus);

        final ScrollView scroll = new ScrollView(this);
        btDeviceList = new LinearLayout(this);
        btDeviceList.setOrientation(LinearLayout.VERTICAL);
        btDeviceList.setGravity(Gravity.CENTER_HORIZONTAL);
        scroll.addView(btDeviceList);
        scroll.setLayoutParams(new LinearLayout.LayoutParams(dp(640), dp(320)));
        root.addView(scroll);

        if (!hasBluetoothPermissions()) {
            btStatus.setText("Bluetooth permission is needed to pair a phone.");
            root.addView(button("Grant Bluetooth permission", v ->
                    requestPermissions(new String[] {
                            Manifest.permission.BLUETOOTH_SCAN,
                            Manifest.permission.BLUETOOTH_CONNECT,
                    }, REQUEST_BT_PERMISSIONS)));
            return root;
        }

        btDiscoveredAddresses.clear();
        root.addView(button("Scan for phones", v -> startBluetoothScan()));
        btStatus.setText(bluetoothAdapter.isEnabled()
                ? "Ready to scan."
                : "Turn on Bluetooth to scan for phones.");
        return root;
    }

    private boolean hasBluetoothPermissions() {
        return checkSelfPermission(Manifest.permission.BLUETOOTH_SCAN) == PackageManager.PERMISSION_GRANTED
                && checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT)
                        == PackageManager.PERMISSION_GRANTED;
    }

    private void startBluetoothScan() {
        if (!hasBluetoothPermissions()) {
            return;
        }
        if (!bluetoothAdapter.isEnabled()) {
            startActivityForResult(new Intent(BluetoothAdapter.ACTION_REQUEST_ENABLE),
                    REQUEST_ENABLE_BT);
            return;
        }
        btDeviceList.removeAllViews();
        btDiscoveredAddresses.clear();
        try {
            if (bluetoothAdapter.isDiscovering()) {
                bluetoothAdapter.cancelDiscovery();
            }
            bluetoothAdapter.startDiscovery();
            btStatus.setText("Scanning for phones…");
        } catch (SecurityException e) {
            Log.w(TAG, "cannot start discovery", e);
        }
    }

    private void onDeviceFound(BluetoothDevice device) {
        if (device == null || btDeviceList == null || !btDiscoveredAddresses.add(device.getAddress())) {
            return;
        }
        String name;
        try {
            name = device.getName();
        } catch (SecurityException e) {
            name = null;
        }
        final String label = (name != null ? name : "Unknown device") + "  (" + device.getAddress() + ")";
        btDeviceList.addView(button(label, v -> pairDevice(device)));
    }

    private void pairDevice(BluetoothDevice device) {
        try {
            if (device.getBondState() == BluetoothDevice.BOND_BONDED) {
                Toast.makeText(this, "Already paired", Toast.LENGTH_SHORT).show();
                return;
            }
            device.createBond();
            if (btStatus != null) {
                btStatus.setText("Pairing… check the phone for a confirmation.");
            }
        } catch (SecurityException e) {
            Log.w(TAG, "cannot pair", e);
        }
    }

    private void onBondStateChanged(Intent intent) {
        if (btStatus == null) {
            return;
        }
        final BluetoothDevice device = intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE);
        final int state = intent.getIntExtra(BluetoothDevice.EXTRA_BOND_STATE, BluetoothDevice.BOND_NONE);
        if (device == null) {
            return;
        }
        String name;
        try {
            name = device.getName();
        } catch (SecurityException e) {
            name = device.getAddress();
        }
        if (state == BluetoothDevice.BOND_BONDED) {
            btStatus.setText("Paired with " + name + ".");
        } else if (state == BluetoothDevice.BOND_NONE) {
            btStatus.setText("Pairing with " + name + " did not complete.");
        }
    }

    // ---- Wizard chrome (title, nav buttons) --------------------------------------------------

    private View buildWizardUi() {
        final LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        // The window is edge-to-edge (enforced from API 35), so keep clear of the car's system bars.
        final int pad = dp(32);
        root.setOnApplyWindowInsetsListener((v, insets) -> {
            final Insets bars = insets.getInsets(WindowInsets.Type.systemBars());
            v.setPadding(pad + bars.left, bars.top + pad / 2, pad + bars.right, bars.bottom + pad / 2);
            return WindowInsets.CONSUMED;
        });

        stepLabel = text("", 16);
        root.addView(stepLabel);

        titleView = text("", 36);
        root.addView(titleView);

        subtitleView = text("", 20);
        root.addView(subtitleView);

        contentFrame = new FrameLayout(this);
        final LinearLayout.LayoutParams contentLp =
                new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f);
        contentLp.topMargin = dp(24);
        contentLp.bottomMargin = dp(24);
        contentFrame.setLayoutParams(contentLp);
        root.addView(contentFrame);

        final LinearLayout nav = new LinearLayout(this);
        nav.setOrientation(LinearLayout.HORIZONTAL);
        nav.setGravity(Gravity.CENTER_HORIZONTAL); // CENTER + the buttons' top margin clips them
        backButton = button("Back", v -> goBack());
        skipButton = button("Skip", v -> advance(false));
        nextButton = button("Next", v -> advance(true));
        nav.addView(backButton);
        nav.addView(skipButton);
        nav.addView(nextButton);
        root.addView(nav);

        return root;
    }

    private void goBack() {
        if (stepIndex > 0) {
            showStep(stepIndex - 1);
        }
    }

    private void advance(boolean runOnNext) {
        final Step step = steps.get(stepIndex);
        if (runOnNext && step.onNext != null) {
            step.onNext.run();
        }
        if (stepIndex == steps.size() - 1) {
            complete();
            return;
        }
        showStep(stepIndex + 1);
    }

    private void showStep(int index) {
        stepIndex = index;
        final Step step = steps.get(index);
        stepLabel.setText("Step " + (index + 1) + " of " + steps.size());
        titleView.setText(step.title);
        subtitleView.setText(step.subtitle);

        contentFrame.removeAllViews();
        btStatus = null;
        btDeviceList = null;
        contentFrame.addView(step.content.build(step));

        final boolean last = index == steps.size() - 1;
        backButton.setVisibility(index == 0 ? View.INVISIBLE : View.VISIBLE);
        skipButton.setVisibility(step.skippable && !last ? View.VISIBLE : View.INVISIBLE);
        nextButton.setText(last ? "Finish setup" : "Next");
    }

    /** Marks the device and this user provisioned, disables this activity, opens the launcher. */
    private void complete() {
        final ContentResolver cr = getContentResolver();
        Settings.Global.putInt(cr, Settings.Global.DEVICE_PROVISIONED, 1);
        Settings.Secure.putInt(cr, USER_SETUP_COMPLETE, 1);
        // Disable first so the HOME intent below cannot resolve back to us.
        getPackageManager().setComponentEnabledSetting(
                new ComponentName(this, SetupActivity.class),
                PackageManager.COMPONENT_ENABLED_STATE_DISABLED,
                PackageManager.DONT_KILL_APP);
        startActivity(new Intent(Intent.ACTION_MAIN)
                .addCategory(Intent.CATEGORY_HOME)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP));
        finish();
    }

    // ---- Small view helpers -------------------------------------------------------------------

    private View singleButtonStep(String label, View.OnClickListener l) {
        final LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER_HORIZONTAL);
        root.addView(button(label, l));
        return root;
    }

    private void open(Intent intent) {
        try {
            startActivity(intent);
        } catch (ActivityNotFoundException e) {
            Log.w(TAG, "cannot open " + intent, e);
            Toast.makeText(this, "Not available on this device", Toast.LENGTH_LONG).show();
        }
    }

    private TextView text(String s, float sp) {
        final TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, sp);
        t.setGravity(Gravity.CENTER);
        t.setPadding(0, dp(12), 0, dp(24));
        return t;
    }

    private Button button(String s, View.OnClickListener l) {
        final Button b = new Button(this);
        b.setText(s);
        b.setTextSize(TypedValue.COMPLEX_UNIT_SP, 22);
        b.setOnClickListener(l);
        final LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(dp(400), dp(96));
        lp.topMargin = dp(20);
        lp.leftMargin = dp(12);
        lp.rightMargin = dp(12);
        b.setLayoutParams(lp);
        return b;
    }

    private <T> Spinner spinner(List<T> items, int selected) {
        final Spinner spinner = new Spinner(this);
        final ArrayAdapter<T> adapter =
                new ArrayAdapter<>(this, android.R.layout.simple_spinner_item, items) {
                    @Override
                    public View getView(int position, View convertView, android.view.ViewGroup parent) {
                        return large(super.getView(position, convertView, parent));
                    }

                    @Override
                    public View getDropDownView(int position, View convertView,
                            android.view.ViewGroup parent) {
                        final View v = large(super.getDropDownView(position, convertView, parent));
                        v.setPadding(dp(16), dp(16), dp(16), dp(16)); // touch-sized rows
                        return v;
                    }

                    private View large(View v) {
                        ((TextView) v).setTextSize(TypedValue.COMPLEX_UNIT_SP, 22);
                        return v;
                    }
                };
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        spinner.setAdapter(adapter);
        spinner.setSelection(Math.max(selected, 0), false);
        spinner.setLayoutParams(
                new LinearLayout.LayoutParams(dp(480), LinearLayout.LayoutParams.WRAP_CONTENT));
        return spinner;
    }

    private View wrapScroll(View content) {
        final ScrollView scroll = new ScrollView(this);
        scroll.addView(content);
        return scroll;
    }

    private int dp(int v) {
        return Math.round(TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v,
                getResources().getDisplayMetrics()));
    }
}
