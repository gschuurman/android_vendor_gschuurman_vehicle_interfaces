package com.gschuurman.carstatus;

/** VHAL property IDs and the VENDOR_MEMS_LIVE layout (automotive/vhal/MemsDecoder.h). */
public final class Vhal {
    private Vhal() {}

    public static final int IGNITION_STATE = 0x11400409;        // VehicleIgnitionState
    public static final int ENGINE_COOLANT_TEMP = 0x11600301;
    public static final int ENGINE_RPM = 0x11600305;
    public static final int PERF_VEHICLE_SPEED = 0x11600207;

    /** FLOAT_VEC, index = MEMS_* below, at most 10 Hz. */
    public static final int VENDOR_MEMS_LIVE = 0x21610614;
    /** BYTES: {ecu, seq, t_ms(4, LE), command echo, response...}, every frame. */
    public static final int VENDOR_MEMS_RAW = 0x21700615;
    /** INT32_VEC {state, ECU id}; state: KLINE_ST_*. */
    public static final int KLINE_STATE = 0x21410610;
    public static final int KLINE_MODE = 0x21400611;
    public static final int KLINE_CMD = 0x21400612;
    public static final int MCU_BATTERY_MV = 0x21400600;

    public static final int KLINE_ST_OFF = 0;
    public static final int KLINE_ST_WAKING = 1;
    public static final int KLINE_ST_CONNECTED = 2;
    public static final int KLINE_ST_RETRY = 3;
    public static final int KLINE_CMD_CLEAR_FAULTS = 1;

    public static final int IGNITION_ON = 4;
    public static final int IGNITION_START = 5;

    // VENDOR_MEMS_LIVE indices (MemsField in MemsDecoder.h; keep in sync)
    public static final int MEMS_RPM = 0;
    public static final int MEMS_COOLANT_C = 1;
    public static final int MEMS_AMBIENT_C = 2;
    public static final int MEMS_INTAKE_AIR_C = 3;
    public static final int MEMS_FUEL_RAIL_C = 4;
    public static final int MEMS_MAP_KPA = 5;
    public static final int MEMS_BATTERY_V = 6;
    public static final int MEMS_THROTTLE_V = 7;
    public static final int MEMS_IDLE_SWITCH = 8;
    public static final int MEMS_FAULTS_1 = 9;
    public static final int MEMS_FAULTS_2 = 10;
    public static final int MEMS_IDLE_SET_RPM = 11;
    public static final int MEMS_IAC_STEPS = 12;
    public static final int MEMS_IGNITION_ADV_DEG = 13;
    public static final int MEMS_COIL_MS = 14;
    public static final int MEMS_THROTTLE_DEG = 15;
    public static final int MEMS_LAMBDA_MV = 16;
    public static final int MEMS_LAMBDA_STATUS = 17;
    public static final int MEMS_CLOSED_LOOP = 18;
    public static final int MEMS_FUEL_TRIM = 19;
    public static final int MEMS_IDLE_POS = 20;
    public static final int MEMS_FAN1 = 21;
    public static final int MEMS_FAN2 = 22;
    public static final int MEMS_FIELD_COUNT = 23;

    public static float[] toFloats(Object value) {
        if (value instanceof Float[]) {
            Float[] in = (Float[]) value;
            float[] out = new float[in.length];
            for (int i = 0; i < in.length; i++) out[i] = in[i] == null ? Float.NaN : in[i];
            return out;
        }
        if (value instanceof float[]) return (float[]) value;
        return null;
    }

    public static float field(float[] v, int i) {
        return v != null && i < v.length ? v[i] : Float.NaN;
    }
}
