# radiation_model.py - Физическая модель радиационных поясов Земли (AE8/AP8)
import math


def calculate_radiation_flux(height_km, lat_deg, b_total_nt):
    """
    Рассчитывает поток электронов высоких энергий (E > 1 МэВ) в зависимости
    от высоты и конфигурации геомагнитного поля в точке.
    Returns: поток электронов (частиц / см² * сек)
    """
    # Расчет параметра L Мак-Илвейна (характеризует геомагнитную оболочку)
    R_earth = 6371.0
    r_ratio = (R_earth + height_km) / R_earth

    # Приблизительный косинус геомагнитной широты
    cos_mag_lat = math.cos(math.radians(lat_deg))
    if cos_mag_lat == 0:
        cos_mag_lat = 0.001

    L = r_ratio / (cos_mag_lat ** 2)
    flux = 0.0

    # Профиль плотности электронов во внутреннем и внешнем поясах
    if 1.2 <= L <= 2.5:
        # Внутренний электронный пояс
        peak_l = 1.5
        flux = 1e6 * math.exp(-((L - peak_l) / 0.3) ** 2)
    elif 3.0 <= L <= 6.5:
        # Внешний пояс (интенсивный, зона ГЛОНАСС)
        peak_l = 4.5
        flux = 1e7 * math.exp(-((L - peak_l) / 0.8) ** 2)

    # Эффект Южно-Атлантической магнитной аномалии (SAA)
    if 300 <= height_km <= 600 and b_total_nt < 25000:
        if 20 <= abs(lat_deg) <= 40:
            flux += 5e4  # Всплеск радиации на высоте МКС

    return round(flux, 2)


if __name__ == "__main__":
    print("Тест радиационного модуля:")
    f_glonass = calculate_radiation_flux(19100.0, 64.0, 1500.0)
    print(f"  -> Поток электронов на орбите ГЛОНАСС: {f_glonass:.2e} част/(см²*сек)")
