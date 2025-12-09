#pragma once

#include <cstdint>

namespace android
{
    namespace hardware
    {
        namespace automotive
        {
            namespace vehicle
            {

                class BH1750_I2C
                {
                public:
                    BH1750_I2C();
                    ~BH1750_I2C();

                    bool openBus(const char *bus, uint8_t addr);
                    bool writeByte(uint8_t byte);
                    int readWord();

                private:
                    int mFd;
                    uint8_t mAddress;
                };

            } // vehicle
        } // automotive
    } // hardware
} // android
