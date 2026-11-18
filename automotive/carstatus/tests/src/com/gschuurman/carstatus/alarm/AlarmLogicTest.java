package com.gschuurman.carstatus.alarm;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import com.gschuurman.carstatus.alarm.AlarmLogic.Level;
import com.gschuurman.carstatus.alarm.AlarmLogic.Reason;
import com.gschuurman.carstatus.alarm.AlarmLogic.Result;

import org.junit.Before;
import org.junit.Test;

import java.util.ArrayList;
import java.util.List;

public class AlarmLogicTest {
    private final List<Result> mEvents = new ArrayList<>();
    private AlarmLogic mLogic;
    private long mT;

    @Before
    public void setUp() {
        mLogic = new AlarmLogic(new AlarmLogic.Config(), mEvents::add);
        mT = 0;
        mLogic.onTick(mT, true);
    }

    /** Samples every 100 ms for ms, coolant ramping linearly from c0 to c1. */
    private void drive(long ms, float c0, float c1, float rpm) {
        for (long i = 0; i <= ms; i += 100) {
            mT += 100;
            mLogic.onSample(mT, c0 + (c1 - c0) * i / (float) ms, rpm, 0);
            if (i % 1000 == 0) mLogic.onTick(mT, true);
        }
    }

    private int pauses() {
        int n = 0;
        for (Result r : mEvents) if (r.pauseMedia) n++;
        return n;
    }

    @Test
    public void normalDriveIsQuiet() {
        drive(10 * 60_000, 20, 90, 2500);   // warm-up over 10 min
        drive(30 * 60_000, 90, 98, 2500);   // fan cycling range
        assertEquals(Level.NONE, mLogic.level());
        assertTrue(mEvents.isEmpty());
    }

    @Test
    public void cautionThenAlarmThenRecovery() {
        drive(10 * 60_000, 20, 95, 2500);
        drive(5 * 60_000, 95, 106, 2500);    // slow climb: no rising-fast
        assertEquals(Level.CAUTION, mLogic.level());
        assertEquals(Reason.COOLANT_WARM, mLogic.reason());
        assertEquals(0, pauses());
        drive(60_000, 106, 111, 2500);
        assertEquals(Level.ALARM, mLogic.level());
        assertEquals(Reason.COOLANT_HIGH, mLogic.reason());
        assertTrue(mLogic.visible());
        assertEquals(1, pauses());
        drive(60_000, 111, 108.5f, 2500);    // within hysteresis: still ALARM
        assertEquals(Level.ALARM, mLogic.level());
        drive(60_000, 108.5f, 104, 2500);
        assertEquals(Level.CAUTION, mLogic.level());  // 104 > 105-3: caution hysteresis
        drive(60_000, 104, 95, 2500);
        assertEquals(Level.NONE, mLogic.level());
        assertFalse(mLogic.visible());
    }

    @Test
    public void acknowledgeHidesAndRearmsOnFurtherRise() {
        drive(10 * 60_000, 20, 109, 2500);
        drive(60_000, 109, 111, 2500);
        assertEquals(Level.ALARM, mLogic.level());
        mLogic.acknowledge(mT);
        assertFalse(mLogic.visible());
        drive(20_000, 111, 112, 2500);
        assertFalse(mLogic.visible());
        int p = pauses();
        drive(20_000, 112, 114.5f, 2500);    // +3 C over the acknowledged value
        assertTrue(mLogic.visible());
        assertEquals(p + 1, pauses());
    }

    @Test
    public void acknowledgedAlarmComesBackAfterTwoMinutes() {
        drive(10 * 60_000, 20, 111, 2500);
        mLogic.acknowledge(mT);
        drive(110_000, 111, 111, 2500);
        assertFalse(mLogic.visible());
        drive(15_000, 111, 111, 2500);
        assertTrue(mLogic.visible());
    }

    @Test
    public void backIntoAlarmAfterAckIsShownNotJustPaused() {
        drive(10 * 60_000, 20, 111, 2500);
        mLogic.acknowledge(mT);
        drive(60_000, 111, 104, 2500);      // down to caution
        assertEquals(Level.CAUTION, mLogic.level());
        drive(60_000, 104, 111, 2500);      // back up
        assertEquals(Level.ALARM, mLogic.level());
        assertTrue(mLogic.visible());
        Result last = mEvents.get(mEvents.size() - 1);
        for (Result r : mEvents) if (r.pauseMedia) assertTrue(r.visible);
        assertTrue(last.visible);
    }

    @Test
    public void coolantReadingDropWhileWarmIsAnAlarm() {
        drive(10 * 60_000, 20, 92, 2500);
        drive(10_000, 92, 70, 2500);         // steam pocket: reading collapses
        assertEquals(Level.ALARM, mLogic.level());
        assertEquals(Reason.COOLANT_DROP, mLogic.reason());
        assertEquals(1, pauses());
    }

    @Test
    public void dropWithEngineOffIsNotAnAlarm() {
        drive(10 * 60_000, 20, 92, 2500);
        drive(10_000, 92, 92, 0);             // engine stopped, ignition still on
        drive(30_000, 92, 70, 0);
        assertEquals(Level.NONE, mLogic.level());
    }

    @Test
    public void fastRiseIsACaution() {
        drive(10 * 60_000, 20, 95, 2500);
        drive(40_000, 95, 104, 2500);         // +9 C in 40 s
        assertEquals(Level.CAUTION, mLogic.level());
        assertEquals(Reason.COOLANT_RISING_FAST, mLogic.reason());
        assertEquals(0, pauses());
    }

    @Test
    public void dataLostWhileRunningIsACaution() {
        drive(5 * 60_000, 20, 85, 2500);
        for (int i = 0; i < 6; i++) {
            mT += 1000;
            mLogic.onTick(mT, true);
        }
        assertEquals(Level.CAUTION, mLogic.level());
        assertEquals(Reason.DATA_LOST, mLogic.reason());
        drive(2_000, 85, 85, 2500);           // data back
        assertEquals(Level.NONE, mLogic.level());
    }

    @Test
    public void ignitionOffIsNotDataLost() {
        drive(5 * 60_000, 20, 85, 2500);
        mT += 500;
        mLogic.onTick(mT, false);
        for (int i = 0; i < 10; i++) {
            mT += 1000;
            mLogic.onTick(mT, false);
        }
        assertEquals(Level.NONE, mLogic.level());
    }

    @Test
    public void sensorFaultBitIsACaution() {
        drive(60_000, 20, 40, 900);
        mT += 100;
        mLogic.onSample(mT, 40, 900, 0x01);
        assertEquals(Level.CAUTION, mLogic.level());
        assertEquals(Reason.SENSOR_FAULT, mLogic.reason());
    }
}
