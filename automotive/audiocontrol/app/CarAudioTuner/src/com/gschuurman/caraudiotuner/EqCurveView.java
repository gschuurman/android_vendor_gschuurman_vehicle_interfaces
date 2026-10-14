package com.gschuurman.caraudiotuner;

import android.content.Context;
import android.content.res.TypedArray;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Path;
import android.util.AttributeSet;
import android.view.View;

/**
 * Frequency response of the equalizer (20 Hz - 20 kHz, log scale, -18..+18 dB), as computed by
 * EqResponse, with grid lines at the bands and every 6 dB.
 */
public final class EqCurveView extends View {
    private static final double MIN_HZ = 20, MAX_HZ = 20000;
    private static final float RANGE_DB = 18;

    private final Paint mGrid = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint mZero = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint mCurve = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint mText = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Path mPath = new Path();
    private final float mDensity;
    private EqResponse mResponse;

    public EqCurveView(Context context, AttributeSet attrs) {
        super(context, attrs);
        mDensity = getResources().getDisplayMetrics().density;
        final TypedArray a = context.obtainStyledAttributes(new int[] {
                android.R.attr.colorAccent, android.R.attr.textColorSecondary});
        final int accent = a.getColor(0, 0xff4285f4);
        final int secondary = a.getColor(1, 0xb3ffffff);
        a.recycle();
        mGrid.setColor(secondary);
        mGrid.setAlpha(40);
        mGrid.setStrokeWidth(mDensity);
        mZero.setColor(secondary);
        mZero.setAlpha(110);
        mZero.setStrokeWidth(mDensity);
        mCurve.setColor(accent);
        mCurve.setStyle(Paint.Style.STROKE);
        mCurve.setStrokeWidth(3 * mDensity);
        mCurve.setStrokeJoin(Paint.Join.ROUND);
        mText.setColor(secondary);
        mText.setTextSize(24 * mDensity);
    }

    public void setResponse(EqResponse response) {
        mResponse = response;
        invalidate();
    }

    private float x(double hz, float left, float width) {
        return left + (float) (Math.log(hz / MIN_HZ) / Math.log(MAX_HZ / MIN_HZ)) * width;
    }

    private float y(double db, float top, float height) {
        final double clamped = Math.max(-RANGE_DB, Math.min(RANGE_DB, db));
        return top + (float) ((RANGE_DB - clamped) / (2 * RANGE_DB)) * height;
    }

    @Override
    protected void onDraw(Canvas canvas) {
        final float left = 60 * mDensity, top = 10 * mDensity;
        final float width = getWidth() - left - 6 * mDensity, height = getHeight() - 2 * top;
        for (int db = -12; db <= 12; db += 6) {
            final float yy = y(db, top, height);
            canvas.drawLine(left, yy, left + width, yy, db == 0 ? mZero : mGrid);
            canvas.drawText((db > 0 ? "+" : "") + db, 2 * mDensity, yy + 8 * mDensity, mText);
        }
        for (float hz : CarAudioParams.EQ_FREQUENCIES_HZ) {
            final float xx = x(hz, left, width);
            canvas.drawLine(xx, top, xx, top + height, mGrid);
        }
        if (mResponse == null) return;
        mPath.reset();
        final int points = Math.max(2, (int) width / 2);
        for (int i = 0; i < points; ++i) {
            final double hz = MIN_HZ * Math.pow(MAX_HZ / MIN_HZ, i / (points - 1.0));
            final float xx = left + i * width / (points - 1), yy = y(mResponse.responseDb(hz), top, height);
            if (i == 0) mPath.moveTo(xx, yy); else mPath.lineTo(xx, yy);
        }
        canvas.drawPath(mPath, mCurve);
    }
}
