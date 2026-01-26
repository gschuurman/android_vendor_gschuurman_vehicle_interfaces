#include "bh1750d.h"
#include "bh1750_i2c.h"
#include <android-base/logging.h>

namespace android
{
    namespace hardware
    {
        namespace automotive
        {
            namespace vehicle
            {

                BH1750::BH1750() : mFd(-1), mAddress(0x23) {}
                BH1750::~BH1750()
                {
                    if (mFd >= 0)
                        close(mFd);
                }

                bool BH1750::begin(const char *i2cBus, uint8_t address)
                {
                    mAddress = address;
                    BH1750_I2C i2c;
                    if (!i2c.openBus(i2cBus, mAddress))
                        return false;
                    // Power on
                    return writeCommand(0x01);
                }

                bool BH1750::writeCommand(uint8_t cmd)
                {
                    BH1750_I2C i2c;
                    if (!i2c.openBus("/dev/i2c-1", mAddress))
                        return false;
                    return i2c.writeByte(cmd);
                }

                int BH1750::readLux()
                {
                    BH1750_I2C i2c;
                    if (!i2c.openBus("/dev/i2c-1", mAddress))
                        return -1;
                    int raw = i2c.readWord();
                    if (raw < 0)
                        return -1;
                    return (raw * 10) / 12; // convert to approximate lux
                }

            } // vehicle
        } // automotive
    } // hardware
} // android
