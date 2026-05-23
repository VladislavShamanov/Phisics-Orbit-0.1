# gui_app.py - Часть 1
import wx
import wx.adv
import wx.grid
import json
import os
import math
from datetime import datetime

import matplotlib
matplotlib.use('WXAgg')
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from matplotlib.figure import Figure

from orbit_propagator import get_points_along_orbit
from gost_model import calculate_density


# gui_app.py - Часть 2
class OrbitControlFrame(wx.Frame):
    def __init__(self):
        super().__init__(parent=None, title="🚀 Phisics-Orbit-0.1: Баллистический комплекс", size=(1100, 700))

        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)

        left_panel = wx.Panel(panel)
        left_sizer = wx.BoxSizer(wx.VERTICAL)

        status_box = wx.StaticBox(left_panel, label="🛰 Мониторинг Солнца (GFZ API)")
        status_sizer = wx.StaticBoxSizer(status_box, wx.VERTICAL)
        self.weather_label = wx.StaticText(left_panel,
                                           label="🟢 Магнитное поле спокойное (Kp = 1.0).\nПараметры атмосферы штатные.")
        self.weather_label.SetForegroundColour(wx.Colour(0, 128, 0))
        status_sizer.Add(self.weather_label, 0, wx.ALL, 5)
        left_sizer.Add(status_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.input_notebook = wx.Notebook(left_panel)

        tab_json = wx.Panel(self.input_notebook)
        json_sizer = wx.BoxSizer(wx.VERTICAL)
        json_sizer.Add(wx.StaticText(tab_json, label="Выберите объект из базы:"), 0, wx.ALL, 5)
        self.sat_listbox = wx.ListBox(tab_json, style=wx.LB_SINGLE)
        json_sizer.Add(self.sat_listbox, 1, wx.EXPAND | wx.ALL, 5)
        tab_json.SetSizer(json_sizer)

        tab_tle = wx.Panel(self.input_notebook)
        tle_sizer = wx.BoxSizer(wx.VERTICAL)
        tle_sizer.Add(wx.StaticText(tab_tle, label="Вставьте 2 строки TLE вручную:"), 0, wx.ALL, 5)
        default_tle = ("1 25544U 98067A   26141.50000000  .00012345  00000-0  20000-3 0  9999\n"
                       "2 25544  51.6400  35.1200 0005000  65.4300  45.2100 15.49500000412345")
        self.tle_input = wx.TextCtrl(tab_tle, style=wx.TE_MULTILINE, value=default_tle)
        tle_sizer.Add(self.tle_input, 1, wx.EXPAND | wx.ALL, 5)
        tab_tle.SetSizer(tle_sizer)

        tab_kep = wx.Panel(self.input_notebook)
        kep_grid = wx.FlexGridSizer(6, 2, 5, 5)
        kep_labels = ["Полуось a (км):", "Эксцентриситет e:", "Наклонение i (°):", "Узел Ω (°):", "Перицентр ω (°):",
                      "Аномалия M (°)"]
        self.kep_inputs = {}
        for label_text in kep_labels:
            lbl = wx.StaticText(tab_kep, label=label_text)
            txt = wx.TextCtrl(tab_kep, value="6771.0" if "полуось" in label_text.lower() else "0.0")
            kep_grid.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL)
            kep_grid.Add(txt, 1, wx.EXPAND)
            self.kep_inputs[label_text] = txt
        kep_grid.AddGrowableCol(1, 1)
        tab_kep.SetSizer(kep_grid)

        self.input_notebook.AddPage(tab_json, "Библиотека")
        self.input_notebook.AddPage(tab_tle, "Ввод TLE")
        self.input_notebook.AddPage(tab_kep, "Кеплер")
        left_sizer.Add(self.input_notebook, 1, wx.EXPAND | wx.ALL, 10)

        time_box = wx.StaticBox(left_panel, label="📅 Баллистическое время и шаг")
        time_sizer = wx.StaticBoxSizer(time_box, wx.VERTICAL)

        self.date_picker = wx.adv.DatePickerCtrl(left_panel, style=wx.adv.DP_DROPDOWN)
        time_sizer.Add(wx.StaticText(left_panel, label="Дата симуляции:"), 0, wx.LEFT, 5)
        time_sizer.Add(self.date_picker, 0, wx.EXPAND | wx.ALL, 5)

        step_sizer = wx.BoxSizer(wx.HORIZONTAL)
        step_sizer.Add(wx.StaticText(left_panel, label="Шаг расчета (сек):"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.step_input = wx.TextCtrl(left_panel, value="120")
        step_sizer.Add(self.step_input, 1, wx.EXPAND)
        time_sizer.Add(step_sizer, 0, wx.EXPAND | wx.ALL, 5)

        left_sizer.Add(time_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.run_btn = wx.Button(left_panel, label="🚀 ЗАПУСТИТЬ МОДЕЛИРОВАНИЕ")
        self.run_btn.SetBackgroundColour(wx.Colour(2, 132, 199))
        self.run_btn.SetForegroundColour(wx.WHITE)
        self.run_btn.Bind(wx.EVT_BUTTON, self.on_run_simulation)
        left_sizer.Add(self.run_btn, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        left_panel.SetSizer(left_sizer)

        # gui_app.py - Часть 3
        self.right_notebook = wx.Notebook(panel)

        self.tab_graph = wx.Panel(self.right_notebook)
        graph_sizer = wx.BoxSizer(wx.VERTICAL)
        self.figure = Figure(figsize=(5, 4), dpi=100)
        self.axes = self.figure.add_subplot(111)
        self.axes.set_title("Профиль плотности вдоль витка ИСЗ")
        self.axes.set_xlabel("Время симуляции (сек)")
        self.axes.set_ylabel("Плотность атмосферы, кг/м³")
        self.axes.grid(True)
        self.canvas = FigureCanvas(self.tab_graph, -1, self.figure)
        graph_sizer.Add(self.canvas, 1, wx.EXPAND | wx.ALL, 5)
        self.tab_graph.SetSizer(graph_sizer)

        tab_table = wx.Panel(self.right_notebook)
        table_sizer = wx.BoxSizer(wx.VERTICAL)
        self.grid = wx.grid.Grid(tab_table)
        self.grid.CreateGrid(0, 5)
        self.grid.SetColLabelValue(0, "Время")
        self.grid.SetColLabelValue(1, "Высота (км)")
        self.grid.SetColLabelValue(2, "Широта")
        self.grid.SetColLabelValue(3, "Долгота")
        self.grid.SetColLabelValue(4, "Плотность (кг/м³)")
        table_sizer.Add(self.grid, 1, wx.EXPAND | wx.ALL, 5)
        tab_table.SetSizer(table_sizer)

        self.right_notebook.AddPage(self.tab_graph, "Графический анализ")
        self.right_notebook.AddPage(tab_table, "Таблица данных")

        main_sizer.Add(left_panel, 0, wx.EXPAND)
        main_sizer.Add(self.right_notebook, 1, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(main_sizer)
        self.load_satellites_from_json()
        self.Show()

    def load_satellites_from_json(self):
        json_path = os.path.join(os.path.dirname(__file__), 'satellites.json')
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                self.sat_data = json.load(f)
                for norad_id, info in self.sat_data.items():
                    idx = self.sat_listbox.Append(f"{info['name']} (NORAD: {norad_id})")
                    self.sat_listbox.SetClientData(idx, info)
                if self.sat_listbox.GetCount() > 0:
                    self.sat_listbox.SetSelection(0)

    # gui_app.py - Часть 4
    def on_run_simulation(self, event):
        selected_tab = self.input_notebook.GetSelection()
        tle_l1, tle_l2 = "", ""

        if selected_tab == 0:
            list_idx = self.sat_listbox.GetSelection()
            if list_idx == wx.NOT_FOUND:
                wx.MessageBox("Пожалуйста, выберите спутник из списка!", "Ошибка", wx.OK | wx.ICON_ERROR)
                return
            info = self.sat_listbox.GetClientData(list_idx)
            tle_l1 = info['tle_l1']
            tle_l2 = info['tle_l2']
        elif selected_tab == 1:
            lines = self.tle_input.GetValue().strip().split('\n')
            if len(lines) < 2:
                wx.MessageBox("TLE должно состоять минимум из двух строк!", "Ошибка", wx.OK | wx.ICON_ERROR)
                return
            tle_l1, tle_l2 = lines[0], lines[1]
        elif selected_tab == 2:
            wx.MessageBox(
                "Расчет по Кеплеровым элементам будет добавлен на следующем этапе.\nИспользуйте пока вкладку TLE или Библиотеку.",
                "Инфо", wx.OK | wx.ICON_INFORMATION)
            return

        try:
            step_sec = int(self.step_input.GetValue())
        except ValueError:
            step_sec = 120

        start_time = datetime.utcnow()
        try:
            orbit_points = get_points_along_orbit(tle_l1, tle_l2, start_time, 45, step_sec)
        except Exception as ex:
            wx.MessageBox(f"Ошибка расчета орбиты: {ex}", "Ошибка", wx.OK | wx.ICON_ERROR)
            return

        if self.grid.GetNumberRows() > 0:
            self.grid.DeleteRows(0, self.grid.GetNumberRows())
        self.axes.clear()

        x_time, y_density = [], []
        f107, f81, kp, doy = 150.0, 150.0, 1.0, 140.0

        for i, pt in enumerate(orbit_points):
            density = calculate_density(pt['height'], f107, f81, kp, doy)
            time_elapsed = i * step_sec
            x_time.append(time_elapsed)
            y_density.append(density)

            self.grid.AppendRows(1)
            row_idx = self.grid.GetNumberRows() - 1
            self.grid.SetCellValue(row_idx, 0, pt['time'])
            self.grid.SetCellValue(row_idx, 1, f"{pt['height']:.2f}")
            self.grid.SetCellValue(row_idx, 2, f"{pt['lat']:.2f}")
            self.grid.SetCellValue(row_idx, 3, f"{pt['lon']:.2f}")
            self.grid.SetCellValue(row_idx, 4, f"{density:.4e}")

        self.axes.plot(x_time, y_density, label="ГОСТ Р 25645.166", color='#0284c7', linewidth=2)
        self.axes.set_title("Профиль плотности вдоль траектории ИСЗ")
        self.axes.set_xlabel("Время полета от точки старта (сек)")
        self.axes.set_ylabel("Плотность атмосферы, кг/м³")
        self.axes.legend()
        self.axes.grid(True)

        self.canvas.draw()
        wx.Bell()

        def export_table_to_csv(self, event):
            """Экспортирует данные из таблицы в CSV файл, совместимый с Excel и OriginPro"""
            num_rows = self.grid.GetNumberRows()
            if num_rows == 0:
                wx.MessageBox("Таблица пуста! Нечего экспортировать.", "Внимание", wx.OK | wx.ICON_WARNING)
                return

            # Открываем стандартный системный диалог сохранения файла
            with wx.FileDialog(self, "Сохранить баллистические данные", wildcard="CSV файлы (*.csv)|*.csv",
                               style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fileDialog:

                if fileDialog.ShowModal() == wx.ID_CANCEL:
                    return  # Пользователь отменил сохранение

                path = fileDialog.GetPath()
                try:
                    with open(path, 'w', encoding='utf-8-sig') as f:  # utf-8-sig чтобы Excel сразу читал кириллицу
                        # Пишем заголовки колонок (через точку с запятой)
                        headers = ["Время", "Высота (км)", "Широта", "Долгота", "Плотность (кг/м³)"]
                        f.write(";".join(headers) + "\n")

                        # Бежим по строкам таблицы и записываем данные
                        for r in range(num_rows):
                            row_data = [self.grid.GetCellValue(r, c) for c in range(5)]
                            f.write(";".join(row_data) + "\n")

                    wx.MessageBox(
                        "Данные успешно экспортированы!\nВы можете открыть этот файл напрямую в Excel или импортировать в Origin Pro.",
                        "Успех", wx.OK | wx.ICON_INFORMATION)
                except Exception as e:
                    wx.MessageBox(f"Не удалось сохранить файл: {e}", "Ошибка", wx.OK | wx.ICON_ERROR)

        def add_satellite_by_norad(self, norad_id):
            """Скачивает свежий TLE с Celestrak по NORAD ID и сохраняет в JSON базу"""
            import requests
            url = f"https://celestrak.org{norad_id}&FORMAT=TLE"

            try:
                response = requests.get(url, timeout=10)
                if response.status_code != 200 or "No data found" in response.text:
                    wx.MessageBox(f"Спутник с NORAD ID {norad_id} не найден на Celestrak!", "Ошибка API",
                                  wx.OK | wx.ICON_ERROR)
                    return False

                lines = response.text.strip().split('\n')
                if len(lines) >= 3:
                    name = lines.strip()  # Имя спутника из первой строки Celestrak
                    tle_l1 = lines.strip()
                    tle_l2 = lines.strip()

                    # Читаем текущую базу JSON
                    json_path = os.path.join(os.path.dirname(__file__), 'satellites.json')
                    sat_data = {}
                    if os.path.exists(json_path):
                        with open(json_path, 'r', encoding='utf-8') as f:
                            sat_data = json.load(f)

                    # Добавляем или обновляем спутник
                    sat_data[str(norad_id)] = {
                        "name": name,
                        "tle_l1": tle_l1,
                        "tle_l2": tle_l2
                    }

                    # Записываем обратно в файл
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(sat_data, f, ensure_ascii=False, indent=2)

                    # Перезагружаем список на экране
                    self.sat_listbox.Clear()
                    self.load_satellites_from_json()
                    wx.MessageBox(f"Объект {name} успешно добавлен/обновлен!", "Успех API", wx.OK | wx.ICON_INFORMATION)
                    return True
            except Exception as e:
                wx.MessageBox(f"Ошибка сети при обновлении TLE: {e}", "Ошибка", wx.OK | wx.ICON_ERROR)
            return False


if __name__ == "__main__":
    app = wx.App()
    frame = OrbitControlFrame()
    app.MainLoop()
