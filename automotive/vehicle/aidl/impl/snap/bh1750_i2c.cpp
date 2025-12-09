#include "bh1750_i2c.h"
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <linux/i2c-dev.h>
#include <android-base/logging.h>

namespace android
{
    namespace hardware
    {
        namespace automotive
        {
            namespace vehicle
            {

                BH1750_I2C::BH1750_I2C() : mFd(-1), mAddress(0) {}
                BH1750_I2C::~BH1750_I2C()
                {
                    if (mFd >= 0)
                        close(mFd);
                }

                bool BH1750_I2C::openBus(const char *bus, uint8_t addr)
                {
                    mFd = open(bus, O_RDWR);
                    if (mFd < 0)
                    {
                        LOG(ERROR) << "Failed to open i2c bus " << bus;
                        return false;
                    }
                    mAddress = addr;
                    if (ioctl(mFd, I2C_SLAVE, mAddress) < 0)
                    {
                        LOG(ERROR) << "Failed to set i2c address " << int(addr);
                        close(mFd);
                        mFd = -1;
                        return false;
                    }
                    return true;
                }

                bool BH1750_I2C::writeByte(uint8_t byte)
                {
                    if (mFd < 0)
                        return false;
                    ssize_t ret = write(mFd, &byte, 1);
                    return ret == 1;
                }

                int BH1750_I2C::readWord()
                {
                    if (mFd < 0)
                        return -1;
                    uint8_t buf[2];
                    ssize_t ret = read(mFd, buf, 2);
                    if (ret != 2)
                        return -1;
                    return (buf[0] << 8) | buf[1];
                }

            } // vehicle
        } // automotive
    } // hardware
} // android
