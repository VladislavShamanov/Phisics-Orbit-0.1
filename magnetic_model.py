# magnetic_model.py
import ppigrf
import math
from datetime import datetime


def calculate_magnetic_field(height_km, lat_deg, lon_deg, sim_date=None):
    """
    Расчет компонентов магнитного поля Земли по модели IGRF-13
    height_km: высота над поверхностью Земли (км)
    lat_deg: географическая широта (градусы, от -90 до 90)
    lon_deg: географическая долгота (градусы, от -180 до 180)
    sim_date: объект datetime (если None, берется текущее время)

    Возвращает: словарь с компонентами Bx, By, Bz и полной индукцией B (в нТл)
    """
    if sim_date is None:
        sim_date = datetime.utcnow()

    # Модель ppigrf требует на вход массивы или списки, а также геоцентрический радиус (в км)
    # Радиус Земли примем за 6371.2 км согласно стандарту IGRF
    r = [6371.2 + height_km]
    theta = [90.0 - lat_deg]  # Коширота (colatitude) в градусах от северного полюса
    phi = [lon_deg]

    try:
        # Вызываем ядро IGRF
        Be, Bn, Bu = ppigrf.igrf(r, theta, phi, sim_date)

        # Метод .item() гарантированно вытаскивает число float из любого массива NumPy
        Bx = float(Bn.item())  # Северный компонент
        By = float(Be.item())  # Восточный компонент
        Bz = float(-Bu.item())  # Вертикальный компонент

        # Полный модуль индукции магнитного поля (закон Пифагора в 3D)
        B_total = math.sqrt(Bx ** 2 + By ** 2 + Bz ** 2)

        return {
            'Bx': Bx,
            'By': By,
            'Bz': Bz,
            'B': B_total
        }


    except Exception as e:
        print(f"Ошибка вычисления IGRF: {e}")
        return {'Bx': 0.0, 'By': 0.0, 'Bz': 0.0, 'B': 0.0}


# Быстрый тест модуля при прямом запуске файла
if __name__ == "__main__":
    # Тестируем поле над Красноярском (широта 56.0, долгота 93.0) на высоте МКС (400 км)
    test_field = calculate_magnetic_field(400.0, 56.0, 93.0)
    print(f"Тест IGRF-13 над Красноярском (400 км):")
    print(f"  -> Полная индукция поля B = {test_field['B']:.2f} нТл")
    print(f"  -> Вертикальный компонент Bz = {test_field['Bz']:.2f} нТл")
