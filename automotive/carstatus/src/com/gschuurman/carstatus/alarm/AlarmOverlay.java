package com.gschuurman.carstatus.alarm;

import android.content.Context;
import android.graphics.Color;
import android.graphics.PixelFormat;
import android.graphics.Typeface;
import android.util.Log;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.gschuurman.carstatus.R;
import com.gschuurman.carstatus.alarm.AlarmLogic.Level;
import com.gschuurman.carstatus.alarm.AlarmLogic.Reason;
import com.gschuurman.carstatus.alarm.AlarmLogic.Result;

/**
 * The warning on top of everything, Android Auto included: full screen and red for ALARM, an amber
 * band at the top for CAUTION. Added from the system user's persistent process with
 * SYSTEM_FLAG_SHOW_FOR_ALL_USERS so it shows on the driver's screen.
 */
final class AlarmOverlay {
    private static final String TAG = "CarStatusAlarm";

    interface OnAcknowledge {
        void onAcknowledge();
    }

    private final Context mContext;
    private final WindowManager mWm;
    private final OnAcknowledge mOnAck;
    private LinearLayout mRoot;
    private TextView mTitle, mValue, mMessage;
    private Button mAck;
    private Level mShownLevel = Level.NONE;

    AlarmOverlay(Context context, OnAcknowledge onAck) {
        mContext = context;
        mWm = context.getSystemService(WindowManager.class);
        mOnAck = onAck;
    }

    void update(Result r) {
        if (!r.visible) {
            hide();
            return;
        }
        if (mRoot == null || mShownLevel != r.level) {
            hide();
            show(r.level);
        }
        fill(r);
    }

    void hide() {
        if (mRoot == null) return;
        try {
            mWm.removeViewImmediate(mRoot);
        } catch (RuntimeException e) {
            Log.w(TAG, "removeView", e);
        }
        mRoot = null;
        mShownLevel = Level.NONE;
    }

    private float sp(float v) {
        return v;
    }

    private int dp(float v) {
        return Math.round(TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v,
                mContext.getResources().getDisplayMetrics()));
    }

    private void show(Level level) {
        final boolean alarm = level == Level.ALARM;
        mRoot = new LinearLayout(mContext);
        mRoot.setOrientation(LinearLayout.VERTICAL);
        mRoot.setGravity(Gravity.CENTER);
        mRoot.setPadding(dp(32), dp(alarm ? 32 : 16), dp(32), dp(alarm ? 32 : 16));
        mRoot.setBackgroundColor(alarm ? 0xF0B71C1C : 0xF0E65100);

        mTitle = text(alarm ? 44 : 28, true);
        mValue = text(alarm ? 120 : 48, true);
        mMessage = text(alarm ? 30 : 22, false);
        mAck = new Button(mContext);
        mAck.setText(R.string.alarm_ack);
        mAck.setTextSize(TypedValue.COMPLEX_UNIT_SP, alarm ? 32 : 22);
        mAck.setAllCaps(false);
        mAck.setPadding(dp(48), dp(16), dp(48), dp(16));
        mAck.setOnClickListener(v -> mOnAck.onAcknowledge());

        if (alarm) {
            mRoot.addView(mTitle);
            mRoot.addView(mValue);
            mRoot.addView(mMessage);
            LinearLayout.LayoutParams bp = new LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
            bp.topMargin = dp(32);
            mRoot.addView(mAck, bp);
        } else {
            mRoot.setOrientation(LinearLayout.HORIZONTAL);
            LinearLayout texts = new LinearLayout(mContext);
            texts.setOrientation(LinearLayout.VERTICAL);
            mTitle.setGravity(Gravity.START);
            mMessage.setGravity(Gravity.START);
            texts.addView(mTitle);
            texts.addView(mMessage);
            mValue.setPadding(0, 0, dp(32), 0);
            mRoot.addView(mValue);
            mRoot.addView(texts, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
            mRoot.addView(mAck);
        }

        WindowManager.LayoutParams lp = new WindowManager.LayoutParams(
                WindowManager.LayoutParams.MATCH_PARENT,
                alarm ? WindowManager.LayoutParams.MATCH_PARENT : WindowManager.LayoutParams.WRAP_CONTENT,
                WindowManager.LayoutParams.TYPE_SYSTEM_ERROR,
                WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN
                        | WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON
                        | WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED
                        | (alarm ? 0 : WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL),
                PixelFormat.TRANSLUCENT);
        lp.gravity = Gravity.TOP;
        lp.privateFlags |= WindowManager.LayoutParams.SYSTEM_FLAG_SHOW_FOR_ALL_USERS;
        lp.setTitle("CarStatusAlarm");
        lp.layoutInDisplayCutoutMode = WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_ALWAYS;
        try {
            mWm.addView(mRoot, lp);
        } catch (RuntimeException e) {
            // Fall back to an application overlay (below the system bars, still above apps).
            Log.w(TAG, "TYPE_SYSTEM_ERROR refused, using TYPE_APPLICATION_OVERLAY", e);
            lp.type = WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY;
            mWm.addView(mRoot, lp);
        }
        mRoot.setSystemUiVisibility(View.SYSTEM_UI_FLAG_LAYOUT_STABLE);
        mShownLevel = level;
    }

    private TextView text(float sizeSp, boolean bold) {
        TextView t = new TextView(mContext);
        t.setTextColor(Color.WHITE);
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, sp(sizeSp));
        t.setGravity(Gravity.CENTER);
        if (bold) t.setTypeface(Typeface.DEFAULT_BOLD);
        return t;
    }

    private void fill(Result r) {
        mTitle.setText(r.level == Level.ALARM ? R.string.alarm_title : R.string.caution_title);
        mValue.setText(Float.isNaN(r.coolantC)
                ? mContext.getString(R.string.value_unknown)
                : mContext.getString(R.string.coolant_value, Math.round(r.coolantC)));
        mMessage.setText(message(r.reason));
    }

    private int message(Reason reason) {
        switch (reason) {
            case COOLANT_HIGH: return R.string.msg_coolant_high;
            case COOLANT_DROP: return R.string.msg_coolant_drop;
            case COOLANT_WARM: return R.string.msg_coolant_warm;
            case COOLANT_RISING_FAST: return R.string.msg_coolant_rising;
            case SENSOR_FAULT: return R.string.msg_sensor_fault;
            case DATA_LOST: return R.string.msg_data_lost;
            default: return R.string.value_unknown;
        }
    }
}
