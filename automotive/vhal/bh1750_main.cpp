#include "bh1750d.h" // Zorg dat dit overeenkomt met je header bestandsnaam!
#include <thread>
#include <chrono>
#include <fstream>
#include <android-base/logging.h>

using namespace android::hardware::automotive::vehicle;

int main()
{
  // Initialiseer logging
  android::base::InitLogging(nullptr, android::base::LogdLogger());
  LOG(INFO) << "Starting BH1750 Light Sensor Daemon...";

  BH1750 sensor;

  // Probeer de sensor te starten op I2C bus 1 (standaard op veel RPi/Boards)
  // Pas "/dev/i2c-1" aan als jouw sensor op een andere bus zit (bijv. /dev/i2c-0)
  if (!sensor.begin("/dev/i2c-1"))
  {
    LOG(ERROR) << "Could not start BH1750 sensor on /dev/i2c-1";
    return 1;
  }

  LOG(INFO) << "BH1750 sensor initialized successfully.";

  // Oneindige lus om de sensor uit te lezen
  while (true)
  {
    int lux = sensor.readLux();

    if (lux >= 0)
    {
      // Schrijf de waarde naar het bestand waar de VHAL deze verwacht
      std::ofstream outfile("/data/vendor/sensors/bh1750_lux");
      if (outfile.is_open())
      {
        outfile << lux << std::endl;
      }
      else
      {
        LOG(ERROR) << "Failed to open /data/vendor/sensors/bh1750_lux for writing";
      }
    }
    else
    {
      LOG(WARNING) << "Failed to read lux value from sensor";
    }

    // Wacht 250ms voor de volgende meting
    std::this_thread::sleep_for(std::chrono::milliseconds(250));
  }

  return 0;
}