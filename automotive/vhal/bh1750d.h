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

                class BH1750
                {
                public:
                    BH1750();
                    ~BH1750();

                    // Initialiseert de sensor op een gegeven i2c bus
                    bool begin(const char *i2cBus, uint8_t address = 0x23);

                    // Leest luxwaarde, return -1 bij fout
                    int readLux();

                private:
                    int mFd;
                    uint8_t mAddress;

                    // interne helper om commandos te sturen
                    bool writeCommand(uint8_t cmd);
                };

            } // vehicle
        } // automotive
    } // hardware
} // android
