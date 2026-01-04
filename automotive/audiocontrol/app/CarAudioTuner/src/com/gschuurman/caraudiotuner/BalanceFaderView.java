package com.gschuurman.caraudiotuner;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.util.AttributeSet;
import android.view.MotionEvent;
import android.view.View;

public class BalanceFaderView extends View {
    private float mBalance = 0f; // -1.0 (Left) to 1.0 (Right)
    private float mFade = 0f;    // -1.0 (Rear) to 1.0 (Front)
    private final Paint mPaint = new Paint();
    private OnValueChangeListener mListener;

    public interface OnValueChangeListener {
        void onValueChanged(float balance, float fade);
    }

    public BalanceFaderView(Context context, AttributeSet attrs) {
        super(context, attrs);
        mPaint.setColor(Color.WHITE);
        mPaint.setStrokeWidth(5f);
    }

    public void setListener(OnValueChangeListener listener) {
        mListener = listener;
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        float width = getWidth();
        float height = getHeight();
        float centerX = width / 2f;
        float centerY = height / 2f;

        // Draw Crosshairs
        canvas.drawLine(centerX, 0, centerX, height, mPaint);
        canvas.drawLine(0, centerY, width, centerY, mPaint);

        // Draw Dot
        float dotX = centerX + (mBalance * (width / 2f));
        float dotY = centerY - (mFade * (height / 2f)); // Up is positive Front

        mPaint.setStyle(Paint.Style.FILL);
        canvas.drawCircle(dotX, dotY, 30f, mPaint);
    }

    @Override
    public boolean onTouchEvent(MotionEvent event) {
        float width = getWidth();
        float height = getHeight();

        mBalance = (event.getX() - (width / 2f)) / (width / 2f);
        mFade = -((event.getY() - (height / 2f)) / (height / 2f));

        mBalance = Math.max(-1f, Math.min(1f, mBalance));
        mFade = Math.max(-1f, Math.min(1f, mFade));

        invalidate();
        if (mListener != null) {
            mListener.onValueChanged(mBalance, mFade);
        }
        return true;
    }
}