package com.gschuurman.carstatus.alarm;

import java.util.ArrayDeque;

/**
 * Engine overheat / coolant-loss alarm rules. Plain Java (no Android), unit tested on the host.
 *
 * <p>Fed with every decoded MEMS sample and a periodic tick. Rules (see mcu/kline-mems-plan.md):
 * <ul>
 *   <li>coolant at or above {@code alarmC}: ALARM; at or above {@code cautionC}: CAUTION. Both
 *       with hysteresis.
 *   <li>coolant rising fast while already warm: CAUTION.
 *   <li>coolant reading dropping sharply while the engine is warm and running: ALARM. When
 *       coolant is lost the sensor can sit in steam or air and read low instead of high (MG F
 *       head gasket failure), so a high-temperature rule alone would miss it.
 *   <li>coolant sensor fault bit from the ECU: CAUTION.
 *   <li>engine data stopping while the engine was running and ACC is on: CAUTION.
 * </ul>
 * A shown alarm can be acknowledged; it comes back when the level goes up, or for ALARM when the
 * coolant climbs a further {@code rearmRiseC} or after {@code rearmMs}.
 */
public final class AlarmLogic {
    public enum Level { NONE, CAUTION, ALARM }

    public enum Reason {
        NONE,
        COOLANT_HIGH,
        COOLANT_DROP,
        COOLANT_WARM,
        COOLANT_RISING_FAST,
        SENSOR_FAULT,
        DATA_LOST,
    }

    public static final class Config {
        public float cautionC = 105f;
        public float alarmC = 110f;
        public float hysteresisC = 3f;
        public float riseC = 8f;              // this much within riseWindowMs...
        public long riseWindowMs = 60_000;
        public float riseMinC = 95f;          // ...while at least this warm
        public float dropC = 15f;             // fall within dropWindowMs while warm and running
        public long dropWindowMs = 30_000;
        public float warmC = 80f;
        public float runningRpm = 500f;
        public long dataLostMs = 5_000;
        public long latchMs = 60_000;         // rising-fast stays for this long
        public float rearmRiseC = 3f;
        public long rearmMs = 120_000;
    }

    /** What the alarm shows now. */
    public static final class Result {
        public final Level level;
        public final Reason reason;
        public final float coolantC;
        /** The overlay should be visible (level above NONE and not acknowledged). */
        public final boolean visible;
        /** One-shot: pause media now (entering ALARM, or ALARM shown again after an ack). */
        public final boolean pauseMedia;

        Result(Level level, Reason reason, float coolantC, boolean visible, boolean pauseMedia) {
            this.level = level;
            this.reason = reason;
            this.coolantC = coolantC;
            this.visible = visible;
            this.pauseMedia = pauseMedia;
        }

        @Override
        public String toString() {
            return level + "/" + reason + " " + coolantC + "C" + (visible ? " shown" : "")
                    + (pauseMedia ? " pause" : "");
        }
    }

    public interface Listener {
        /** Level, reason or visibility changed, or media must be paused. */
        void onAlarm(Result result);
    }

    private static final class Sample {
        final long t;
        final float c;

        Sample(long t, float c) {
            this.t = t;
            this.c = c;
        }
    }

    private final Config mCfg;
    private final Listener mListener;
    private final ArrayDeque<Sample> mHistory = new ArrayDeque<>();

    private float mCoolant = Float.NaN;
    private long mLastSampleT = -1;
    private long mLastRunningT = -1;
    private boolean mWarmSeen;
    private boolean mSensorFault;
    private boolean mAcc;
    private boolean mHighLatched, mWarmLatched;
    private long mRisingUntil = -1;
    private boolean mDropLatched;

    private Level mLevel = Level.NONE;
    private Reason mReason = Reason.NONE;
    private boolean mAcked;
    private Level mAckLevel = Level.NONE;
    private long mAckT;
    private float mAckCoolant;
    private boolean mVisible;

    public AlarmLogic(Config cfg, Listener listener) {
        mCfg = cfg;
        mListener = listener;
    }

    public Level level() { return mLevel; }
    public Reason reason() { return mReason; }
    public boolean visible() { return mVisible; }

    /** One decoded engine sample. NaN coolant = not available in this sample. */
    public void onSample(long t, float coolantC, float rpm, int faults1) {
        mLastSampleT = t;
        if (rpm >= mCfg.runningRpm) mLastRunningT = t;
        mSensorFault = (faults1 & 0x01) != 0;
        if (!Float.isNaN(coolantC)) {
            mCoolant = coolantC;
            if (coolantC >= mCfg.warmC) mWarmSeen = true;
            mHistory.addLast(new Sample(t, coolantC));
            long keep = Math.max(mCfg.riseWindowMs, mCfg.dropWindowMs);
            while (!mHistory.isEmpty() && t - mHistory.peekFirst().t > keep) mHistory.removeFirst();
        }
        evaluate(t);
    }

    /** Call about once a second. */
    public void onTick(long t, boolean acc) {
        if (mAcc && !acc) {
            // Ignition off: the ECU goes quiet on purpose. Start the next drive fresh.
            mHistory.clear();
            mLastRunningT = -1;
            mLastSampleT = -1;
            mWarmSeen = false;
            mDropLatched = false;
            mRisingUntil = -1;
            mSensorFault = false;
        }
        mAcc = acc;
        evaluate(t);
    }

    public void acknowledge(long t) {
        if (mLevel == Level.NONE) return;
        mAcked = true;
        mAckLevel = mLevel;
        mAckT = t;
        mAckCoolant = Float.isNaN(mCoolant) ? Float.NEGATIVE_INFINITY : mCoolant;
        if (mReason == Reason.COOLANT_DROP) mDropLatched = false;  // seen; re-detected if it repeats
        evaluate(t);
    }

    private boolean engineWasRunning(long t) {
        return mLastRunningT >= 0 && mLastSampleT >= 0 && mLastSampleT - mLastRunningT < 2_000;
    }

    private void evaluate(long t) {
        final float c = mCoolant;
        final boolean fresh = mLastSampleT >= 0 && t - mLastSampleT < mCfg.dataLostMs;

        if (fresh && !Float.isNaN(c)) {
            if (c >= mCfg.alarmC) mHighLatched = true;
            else if (c < mCfg.alarmC - mCfg.hysteresisC) mHighLatched = false;
            if (c >= mCfg.cautionC) mWarmLatched = true;
            else if (c < mCfg.cautionC - mCfg.hysteresisC) mWarmLatched = false;

            if (c >= mCfg.riseMinC) {
                float min = Float.POSITIVE_INFINITY;
                for (Sample s : mHistory) {
                    if (t - s.t <= mCfg.riseWindowMs) min = Math.min(min, s.c);
                }
                if (c - min >= mCfg.riseC) mRisingUntil = t + mCfg.latchMs;
            }
            if (mWarmSeen && engineWasRunning(t) && t - mLastRunningT < 2_000) {
                float max = Float.NEGATIVE_INFINITY;
                for (Sample s : mHistory) {
                    if (t - s.t <= mCfg.dropWindowMs) max = Math.max(max, s.c);
                }
                if (max - c >= mCfg.dropC) mDropLatched = true;
            }
        } else if (!fresh) {
            mHighLatched = false;
            mWarmLatched = false;
        }

        boolean dataLost = mAcc && !fresh && engineWasRunning(t)
                && mLastSampleT >= 0 && t - mLastSampleT >= mCfg.dataLostMs;

        Level level = Level.NONE;
        Reason reason = Reason.NONE;
        if (mHighLatched) { level = Level.ALARM; reason = Reason.COOLANT_HIGH; }
        else if (mDropLatched) { level = Level.ALARM; reason = Reason.COOLANT_DROP; }
        else if (mWarmLatched) { level = Level.CAUTION; reason = Reason.COOLANT_WARM; }
        else if (mRisingUntil >= 0 && t < mRisingUntil) { level = Level.CAUTION; reason = Reason.COOLANT_RISING_FAST; }
        else if (dataLost) { level = Level.CAUTION; reason = Reason.DATA_LOST; }
        else if (fresh && mSensorFault) { level = Level.CAUTION; reason = Reason.SENSOR_FAULT; }

        boolean pause = false;
        if (level == Level.NONE) {
            mAcked = false;
        } else if (level == Level.ALARM && mLevel != Level.ALARM) {
            mAcked = false;  // (back) into ALARM: always shown, never only paused
            pause = true;
        } else if (mAcked) {
            boolean rearm = level.ordinal() > mAckLevel.ordinal();
            if (level == Level.ALARM && !Float.isNaN(c)
                    && (c >= mAckCoolant + mCfg.rearmRiseC || t - mAckT >= mCfg.rearmMs)) {
                rearm = true;
            }
            if (rearm) {
                mAcked = false;
                pause = level == Level.ALARM;
            }
        }
        boolean visible = level != Level.NONE && !mAcked;

        boolean changed = level != mLevel || reason != mReason || visible != mVisible;
        mLevel = level;
        mReason = reason;
        mVisible = visible;
        if ((changed || pause) && mListener != null) {
            mListener.onAlarm(new Result(level, reason, c, visible, pause));
        }
    }
}
