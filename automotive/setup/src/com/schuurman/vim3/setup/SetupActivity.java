package com.schuurman.vim3.setup;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.ComponentName;
import android.content.ContentResolver;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.provider.Settings;
import android.util.Log;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

/**
 * First-boot setup: Wi-Fi, then a Google account, then "finish", which marks the device and the
 * current user as provisioned, disables this HOME activity and hands over to the real launcher.
 * The steps are plain buttons that open the system screens; nothing here needs credentials or
 * credential-encrypted storage, so it works while the user is still locked.
 */
public class SetupActivity extends Activity {
    private static final String TAG = "Vim3Setup";
    private static final String USER_SETUP_COMPLETE = "user_setup_complete";
    private static final String GOOGLE_ACCOUNT_TYPE = "com.google";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (isProvisioned()) {
            // Already set up (e.g. an upgrade over an existing device): stay out of the way.
            complete();
            return;
        }
        setContentView(buildUi());
    }

    @Override
    public void onBackPressed() {
        // This is the home screen while unprovisioned; there is nothing to go back to.
    }

    private boolean isProvisioned() {
        final ContentResolver cr = getContentResolver();
        return Settings.Global.getInt(cr, Settings.Global.DEVICE_PROVISIONED, 0) == 1
                && Settings.Secure.getInt(cr, USER_SETUP_COMPLETE, 0) == 1;
    }

    private View buildUi() {
        final LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER_HORIZONTAL);
        final int pad = dp(48);
        root.setPadding(pad, pad, pad, pad);

        root.addView(text("Set up your head unit", 40));
        root.addView(text("Connect to Wi-Fi, then add your Google account. You can skip either "
                + "step and do it later from Settings.", 22));

        root.addView(button("1.  Connect to Wi-Fi", v ->
                open(new Intent(Settings.ACTION_WIFI_SETTINGS))));
        root.addView(button("2.  Add a Google account", v ->
                open(new Intent(Settings.ACTION_ADD_ACCOUNT)
                        .putExtra(Settings.EXTRA_ACCOUNT_TYPES,
                                new String[] {GOOGLE_ACCOUNT_TYPE}))));
        root.addView(button("Finish setup", v -> complete()));
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
        b.setTextSize(TypedValue.COMPLEX_UNIT_SP, 26);
        b.setOnClickListener(l);
        final LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(dp(640), dp(96));
        lp.topMargin = dp(20);
        b.setLayoutParams(lp);
        return b;
    }

    private int dp(int v) {
        return Math.round(TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v,
                getResources().getDisplayMetrics()));
    }
}
