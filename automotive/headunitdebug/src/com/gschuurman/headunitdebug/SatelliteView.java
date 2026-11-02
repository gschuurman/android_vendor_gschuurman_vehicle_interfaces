package com.gschuurman.headunitdebug;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.location.GnssStatus;
import android.util.AttributeSet;
import android.util.TypedValue;
import android.view.View;

import java.util.ArrayList;
import java.util.List;

/** Bar per tracked satellite: height = C/N0 (0-50 dBHz), green when used in the fix. */
public class SatelliteView extends View {
    private static final float MAX_CN0 = 50f;

    private static final class Sat {
        String label;
        float cn0;
        boolean used;
    }

    private final List<Sat> mSats = new ArrayList<>();
    private final Paint mUsed = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint mTracked = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint mText = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint mGrid = new Paint();

    public SatelliteView(Context context) {
        this(context, null);
    }

    public SatelliteView(Context context, AttributeSet attrs) {
        super(context, attrs);
        mUsed.setColor(context.getColor(R.color.dot_ok));
        mTracked.setColor(context.getColor(R.color.dot_off));
        mText.setColor(0xB3FFFFFF);
        mText.setTextAlign(Paint.Align.CENTER);
        mText.setTextSize(TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_SP, 11,
                getResources().getDisplayMetrics()));
        mGrid.setColor(0x33FFFFFF);
        mGrid.setStrokeWidth(1f);
    }

    /** Takes the satellites with a signal from a GnssStatus. */
    public void setStatus(GnssStatus status) {
        mSats.clear();
        for (int i = 0; i < status.getSatelliteCount(); i++) {
            if (status.getCn0DbHz(i) <= 0) continue;
            Sat s = new Sat();
            s.label = constellationLetter(status.getConstellationType(i)) + status.getSvid(i);
            s.cn0 = status.getCn0DbHz(i);
            s.used = status.usedInFix(i);
            mSats.add(s);
        }
        mSats.sort((a, b) -> Float.compare(b.cn0, a.cn0));
        invalidate();
    }

    static String constellationLetter(int type) {
        switch (type) {
            case GnssStatus.CONSTELLATION_GPS: return "G";
            case GnssStatus.CONSTELLATION_GLONASS: return "R";
            case GnssStatus.CONSTELLATION_GALILEO: return "E";
            case GnssStatus.CONSTELLATION_BEIDOU: return "C";
            case GnssStatus.CONSTELLATION_QZSS: return "J";
            case GnssStatus.CONSTELLATION_SBAS: return "S";
            default: return "?";
        }
    }

    @Override
    protected void onDraw(Canvas canvas) {
        final float labelH = mText.getTextSize() * 1.4f;
        final float chartH = getHeight() - labelH;
        // 10 dBHz grid lines; 30+ dBHz is a usable signal.
        for (int db = 10; db <= MAX_CN0; db += 10) {
            float y = chartH - chartH * db / MAX_CN0;
            canvas.drawLine(0, y, getWidth(), y, mGrid);
        }
        if (mSats.isEmpty()) {
            canvas.drawText("no satellites tracked", getWidth() / 2f, chartH / 2f, mText);
            return;
        }
        final int n = Math.min(mSats.size(), 24);
        final float slot = (float) getWidth() / n;
        final float bar = slot * 0.7f;
        for (int i = 0; i < n; i++) {
            Sat s = mSats.get(i);
            float left = i * slot + (slot - bar) / 2f;
            float top = chartH - chartH * Math.min(s.cn0, MAX_CN0) / MAX_CN0;
            canvas.drawRect(left, top, left + bar, chartH, s.used ? mUsed : mTracked);
            canvas.drawText(s.label, i * slot + slot / 2f, getHeight() - labelH * 0.25f, mText);
        }
    }
}
