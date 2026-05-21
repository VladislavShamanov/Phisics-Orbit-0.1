// wrapper.cpp
#include "atmosGOST_R_25645_166_2004.h"
#include <cmath>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

extern "C" {
    __declspec(dllexport) double get_density(
        double height,
        double f107,
        double f81,
        double kp,
        double day_of_year
    ) {
        // 1. Координаты X[3] в КИЛОМЕТРАХ (Радиус Земли 6371 + высота)
        double const r_km = 6371.0 + height;
        double const X[3] = { r_km, 0.0, 0.0 }; // Пусть спутник пока на экваторе

        // 2. Всемирное время в секундах (t_s). Возьмем полдень = 12 часов * 3600 сек
        double const t_s = 12.0 * 3600.0;

        // 3. Звёздное время S_rad (упрощенно возьмем 0.0 для теста)
        double const S_rad = 0.0;

        // 4. Прямое восхождение Солнца alpha_rad (приблизительно зависит от дня года DoY)
        // Должно быть в пределах от 0 до 2*PI
        double const alpha_rad = 2.0 * M_PI * (day_of_year / 365.25);

        // 5. Склонение Солнца delta_rad (колеблется от -23.45 до +23.45 градусов)
        // Переводим в радианы. Находится строго в пределах от -PI до PI
        double const delta_rad = 23.45 * (M_PI / 180.0) * sin(2.0 * M_PI * (day_of_year - 80.0) / 365.25);

        // Передаем ровно 10 параметров в строгом соответствии с ГОСТом!
        return atmosGOST_R_25645_166_2004(
            height,    // 1. h_km
            f107,      // 2. F107
            kp,        // 3. Kp
            f81,       // 4. F81
            day_of_year, // 5. DoY
            X,         // 6. X[3]
            t_s,       // 7. t_s
            S_rad,     // 8. S_rad
            alpha_rad, // 9. alpha_rad
            delta_rad  // 10. delta_rad
        );
    }
}
