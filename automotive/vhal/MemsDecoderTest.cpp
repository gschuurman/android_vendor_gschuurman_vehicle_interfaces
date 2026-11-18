#include "MemsDecoder.h"

#include <gtest/gtest.h>

#include <cmath>
#include <vector>

using namespace android::hardware::automotive::vehicle;

// 0x80 answer as the MCU forwards it: echo, length (28 = 0x1C), then documented offsets 1..0x1B.
static std::vector<uint8_t> frame80() {
    std::vector<uint8_t> f(29, 0);
    f[0] = 0x80;
    f[1] = 0x1C;
    f[0x01 + 1] = 0x03;  // rpm 0x0320 = 800
    f[0x02 + 1] = 0x20;
    f[0x03 + 1] = 145;   // coolant 90 C
    f[0x04 + 1] = 75;    // ambient 20 C
    f[0x05 + 1] = 85;    // intake 30 C
    f[0x06 + 1] = 0xFF;  // no fuel rail sensor
    f[0x07 + 1] = 35;    // MAP kPa
    f[0x08 + 1] = 138;   // 13.8 V
    f[0x09 + 1] = 25;    // 0.5 V
    f[0x0A + 1] = 0x10;  // idle switch closed
    f[0x0D + 1] = 0x01;  // coolant sensor fault
    f[0x0E + 1] = 0x80;
    f[0x0F + 1] = 140;   // 854 rpm idle set point
    f[0x12 + 1] = 30;
    f[0x16 + 1] = 72;    // 12 deg
    f[0x17 + 1] = 0x07;  // 0x07D0 * 0.002 = 4 ms
    f[0x18 + 1] = 0xD0;
    return f;
}

TEST(MemsDecoder, Frame80) {
    auto f = frame80();
    MemsValues v;
    ASSERT_TRUE(memsDecode(f.data(), f.size(), &v));
    EXPECT_TRUE(v.have80);
    EXPECT_FLOAT_EQ(v.v[MEMS_RPM], 800);
    EXPECT_FLOAT_EQ(v.v[MEMS_COOLANT_C], 90);
    EXPECT_FLOAT_EQ(v.v[MEMS_AMBIENT_C], 20);
    EXPECT_FLOAT_EQ(v.v[MEMS_INTAKE_AIR_C], 30);
    EXPECT_TRUE(std::isnan(v.v[MEMS_FUEL_RAIL_C]));
    EXPECT_FLOAT_EQ(v.v[MEMS_MAP_KPA], 35);
    EXPECT_NEAR(v.v[MEMS_BATTERY_V], 13.8f, 1e-4);
    EXPECT_NEAR(v.v[MEMS_THROTTLE_V], 0.5f, 1e-4);
    EXPECT_FLOAT_EQ(v.v[MEMS_IDLE_SWITCH], 1);
    EXPECT_FLOAT_EQ(v.v[MEMS_FAULTS_1], 1);
    EXPECT_FLOAT_EQ(v.v[MEMS_FAULTS_2], 0x80);
    EXPECT_NEAR(v.v[MEMS_IDLE_SET_RPM], 854, 0.01);
    EXPECT_FLOAT_EQ(v.v[MEMS_IAC_STEPS], 30);
    EXPECT_FLOAT_EQ(v.v[MEMS_IGNITION_ADV_DEG], 12);
    EXPECT_NEAR(v.v[MEMS_COIL_MS], 4.0f, 1e-4);
    EXPECT_TRUE(std::isnan(v.v[MEMS_THROTTLE_DEG]));  // no 0x7D yet
}

TEST(MemsDecoder, BelowZeroCoolant) {
    auto f = frame80();
    f[0x03 + 1] = 40;  // -15 C
    MemsValues v;
    ASSERT_TRUE(memsDecode(f.data(), f.size(), &v));
    EXPECT_FLOAT_EQ(v.v[MEMS_COOLANT_C], -15);
}

TEST(MemsDecoder, ShortFrameKeepsLaterFields) {
    auto f = frame80();
    MemsValues v;
    ASSERT_TRUE(memsDecode(f.data(), f.size(), &v));
    // A shorter frame variant (length byte 0x0F): fields past it keep the previous value.
    std::vector<uint8_t> s(f.begin(), f.begin() + 16);
    s[1] = 0x0F;
    s[0x03 + 1] = 150;
    ASSERT_TRUE(memsDecode(s.data(), s.size(), &v));
    EXPECT_FLOAT_EQ(v.v[MEMS_COOLANT_C], 95);
    EXPECT_FLOAT_EQ(v.v[MEMS_IGNITION_ADV_DEG], 12);
}

TEST(MemsDecoder, LengthByteLimitsTheFrame) {
    auto f = frame80();
    f[1] = 0x05;  // claims to end before the battery byte
    MemsValues v;
    EXPECT_FALSE(memsDecode(f.data(), f.size(), &v));
    EXPECT_FALSE(v.have80);
}

TEST(MemsDecoder, Frame7D) {
    std::vector<uint8_t> f(33, 0);
    f[0] = 0x7D;
    f[1] = 0x20;
    f[0x02 + 1] = 20;           // 10 deg throttle
    f[0x05 + 1] = 0xA0;         // fan 1 + fan 2
    f[0x06 + 1] = 90;           // 450 mV
    f[0x09 + 1] = 1;
    f[0x0A + 1] = 1;
    f[0x0C + 1] = 100;
    f[0x0F + 1] = 40;
    MemsValues v;
    ASSERT_TRUE(memsDecode(f.data(), f.size(), &v));
    EXPECT_TRUE(v.have7d);
    EXPECT_FLOAT_EQ(v.v[MEMS_THROTTLE_DEG], 10);
    EXPECT_FLOAT_EQ(v.v[MEMS_FAN1], 1);
    EXPECT_FLOAT_EQ(v.v[MEMS_FAN2], 1);
    EXPECT_FLOAT_EQ(v.v[MEMS_LAMBDA_MV], 450);
    EXPECT_FLOAT_EQ(v.v[MEMS_CLOSED_LOOP], 1);
    EXPECT_FLOAT_EQ(v.v[MEMS_FUEL_TRIM], 100);
    EXPECT_FLOAT_EQ(v.v[MEMS_IDLE_POS], 40);
}

TEST(MemsDecoder, OtherFramesIgnored) {
    uint8_t d0[] = {0xD0, 0x39, 0x00, 0x00, 0x5C};
    MemsValues v;
    EXPECT_FALSE(memsDecode(d0, sizeof(d0), &v));
    uint8_t tiny[] = {0x80};
    EXPECT_FALSE(memsDecode(tiny, sizeof(tiny), &v));
}
