# main.py
from gost_model import calculate_atmosphere_density

if __name__ == "__main__":
    h = 300  # Высота орбиты ИСЗ, км
    f107 = 150  # Средняя солнечная активность
    ap = 4  # Спокойное геомагнитное поле

    density = calculate_atmosphere_density(h, f107, ap)
    print(f"Плотность атмосферы на высоте {h} км: {density:.4e} кг/м³")
