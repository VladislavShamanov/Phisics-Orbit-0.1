# main.py
import math

from datetime import datetime
from orbit_propagator import get_points_along_orbit
from gost_model import calculate_density

if __name__ == "__main__":
    print("=" * 65)
    print("БАЛЛИСТИЧЕСКИЙ СИМУЛЯТОР ОРБИТ И АТМОСФЕРЫ (Phisics-Orbit-0.1)")
    print("=" * 65)

    # 1. Задаем TLE (например, Международная Космическая Станция МКС)
    # Эти две строки описывают текущую орбиту
    # --- ОБНОВИ ЭТИ СТРОЧКИ В main.py НА СВЕЖИЙ TLE ---
    tle_l1 = "1 25544U 98067A   26141.50000000  .00012345  00000-0  20000-3 0  9999"
    tle_l2 = "2 25544  51.6400  35.1200 0005000  65.4300  45.2100 15.49500000412345"

    # 2. Фиксируем параметры симуляции
    start_sim_time = datetime.utcnow()
    duration = 45  # Считаем половину витка (45 минут)
    step_sec = 120  # Шаг расчета в секундах (можно менять: 60, 120, 300)

    # Индексы космической погоды (вручную или из нашего API парсера)
    f107, f81, kp = 150.0, 150.0, 1.0
    day_of_year = 140.0

    print(f"Симуляция запущена для МКС на {duration} минут с шагом {step_sec} сек.")
    print(f"Параметры космоса: F10.7 = {f107}, Kp = {kp}")
    print("=" * 65)

    # 3. Генерируем точки траектории спутника по TLE
    orbit_points = get_points_along_orbit(tle_l1, tle_l2, start_sim_time, duration, step_sec)

    # 4. Выводим шапку таблицы результатов
    print(f"{'Время':<10} | {'Высота, км':<11} | {'Широта':<8} | {'Долгота':<8} | {'Плотность ГОСТ, кг/м³':<20}")
    print("-" * 65)

    # 5. Цикл расчета плотности по всей траектории
    for pt in orbit_points:
        # Вызываем наше С++ ядро ГОСТа для каждой точки орбиты!
        density = calculate_density(
            pt['height'],
            f107,
            f81,
            kp,
            day_of_year
        )

        # Выводим строку результатов в таблицу
        print(f"{pt['time']:<10} | {pt['height']:<11.2f} | {pt['lat']:<8.2f} | {pt['lon']:<8.2f} | {density:.4e}")

    print("=" * 65)
    print("Расчет по орбите успешно завершен!")

    # Добавь этот блок в конец main.py для проверки перед сном:
    from kepler_converter import kepler_to_cartesian

    print("\n" + "=" * 50)
    print("ТЕСТ: Конвертация Кеплеровых элементов")
    print("=" * 50)

    # Задаем параметры: а=6771км, е=0 (круговая), i=51.6 град, остальное по нулям
    pos, vel = kepler_to_cartesian(6771.0, 0.0, 51.6, 0.0, 0.0, 0.0)

    print(f"Положение ИСЗ (X, Y, Z): {pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f} км")
    print(f"Скорость ИСЗ (Vx, Vy, Vz): {vel[0]:.2f}, {vel[1]:.2f}, {vel[2]:.2f} км/с")
    # Первая космическая скорость должна быть около 7.67 км/с!
    v_full = math.sqrt(vel[0] ** 2 + vel[1] ** 2 + vel[2] ** 2)
    print(f"Полная скорость спутника: {v_full:.3f} км/с")
    print("=" * 50)

