package com.gschuurman.caraudiotuner;

import android.content.Context;
import android.content.res.TypedArray;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.RectF;
import android.util.AttributeSet;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;

/**
 * Vertical gain slider of the graphic equalizer: whole dB steps between -max and +max, 0 in the
 * middle. Dragging or tapping sets the value; D-pad/rotary up and down step it by 1 dB.
 */
public final class EqSliderView extends View {
    /** Called for every change made by the user. */
    public interface OnValueChangeListener {
        void onValueChanged(EqSliderView slider, int value);
    }

    private final Paint mTrack = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint mFill = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint mThumb = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint mText = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint mLabel = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final RectF mRect = new RectF();
    private final float mDensity;

    private int mMax = CarAudioParams.EQ_MAX_GAIN_DB;
    private int mValue;
    private String mLabelText = "";
    private OnValueChangeListener mListener;

    public EqSliderView(Context context, AttributeSet attrs) {
        super(context, attrs);
        mDensity = getResources().getDisplayMetrics().density;
        final TypedArray a = context.obtainStyledAttributes(new int[] {
                android.R.attr.colorAccent, android.R.attr.textColorPrimary,
                android.R.attr.textColorSecondary});
        final int accent = a.getColor(0, 0xff4285f4);
        final int primary = a.getColor(1, 0xffffffff);
        final int secondary = a.getColor(2, 0xb3ffffff);
        a.recycle();
        mTrack.setColor(secondary);
        mTrack.setAlpha(70);
        mFill.setColor(accent);
        mThumb.setColor(accent);
        mText.setColor(primary);
        mText.setTextAlign(Paint.Align.CENTER);
        mText.setTextSize(32 * mDensity);
        mLabel.setColor(secondary);
        mLabel.setTextAlign(Paint.Align.CENTER);
        mLabel.setTextSize(30 * mDensity);
        setFocusable(true);
        setClickable(true);
    }

    public void setLabel(String label) {
        mLabelText = label;
        setContentDescription(label);
        invalidate();
    }

    public void setValue(int value) {
        mValue = Math.max(-mMax, Math.min(mMax, value));
        invalidate();
    }

    public int getValue() {
        return mValue;
    }

    public void setOnValueChangeListener(OnValueChangeListener listener) {
        mListener = listener;
    }

    // Track geometry: value text on top, label at the bottom.
    private float trackTop() {
        return 52 * mDensity;
    }

    private float trackBottom() {
        return getHeight() - 52 * mDensity;
    }

    private float yForValue(int value) {
        final float top = trackTop(), bottom = trackBottom();
        return bottom - (value + mMax) * (bottom - top) / (2f * mMax);
    }

    @Override
    protected void onDraw(Canvas canvas) {
        final float cx = getWidth() / 2f;
        final float w = 10 * mDensity;
        mRect.set(cx - w / 2, trackTop(), cx + w / 2, trackBottom());
        canvas.drawRoundRect(mRect, w / 2, w / 2, mTrack);
        final float zero = yForValue(0), y = yForValue(mValue);
        mRect.set(cx - w / 2, Math.min(zero, y), cx + w / 2, Math.max(zero, y));
        canvas.drawRect(mRect, mFill);
        // Center (0 dB) tick.
        canvas.drawRect(cx - 3 * w, zero - mDensity, cx + 3 * w, zero + mDensity, mTrack);
        final float r = (isFocused() ? 22 : 18) * mDensity;
        canvas.drawCircle(cx, y, r, mThumb);
        canvas.drawText((mValue > 0 ? "+" : "") + mValue, cx, 34 * mDensity, mText);
        canvas.drawText(mLabelText, cx, getHeight() - 14 * mDensity, mLabel);
    }

    @Override
    public boolean onTouchEvent(MotionEvent event) {
        if (!isEnabled()) return false;
        switch (event.getActionMasked()) {
            case MotionEvent.ACTION_DOWN:
            case MotionEvent.ACTION_MOVE:
                getParent().requestDisallowInterceptTouchEvent(true);
                final float top = trackTop(), bottom = trackBottom();
                final float f = (bottom - Math.max(top, Math.min(bottom, event.getY())))
                        / (bottom - top);
                change(Math.round(f * 2 * mMax) - mMax);
                return true;
            case MotionEvent.ACTION_UP:
                performClick();
                return true;
            default:
                return true;
        }
    }

    @Override
    public boolean performClick() {
        return super.performClick();
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (isEnabled() && keyCode == KeyEvent.KEYCODE_DPAD_UP) {
            change(mValue + 1);
            return true;
        }
        if (isEnabled() && keyCode == KeyEvent.KEYCODE_DPAD_DOWN) {
            change(mValue - 1);
            return true;
        }
        return super.onKeyDown(keyCode, event);
    }

    private void change(int value) {
        value = Math.max(-mMax, Math.min(mMax, value));
        if (value == mValue) return;
        mValue = value;
        invalidate();
        if (mListener != null) mListener.onValueChanged(this, value);
    }
}
