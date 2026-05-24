import wx
import wx.adv
import wx.grid
import json
import os
from datetime import datetime

import matplotlib

matplotlib.use('WXAgg')
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from matplotlib.figure import Figure

from orbit_propagator import get_points_along_orbit, download_tle_from_celestrak, save_grid_to_csv
from gost_model import calculate_density

# Глобальные настройки по умолчанию (если файла конфигурации нет)
DEFAULT_SETTINGS = {
    "celestrak_url": "https://celestrak.org{norad_id}&FORMAT=TLE"
}


class SettingsDialog(wx.Dialog):
    """Окно настроек путей и адресов загрузки API"""

    def __init__(self, parent, current_settings):
        super().__init__(parent, title="⚙️ Настройки баллистического комплекса", size=(500, 200))
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(wx.StaticText(panel, label="URL сервера обновлений TLE (Celestrak):"), 0, wx.ALL, 10)
        self.url_input = wx.TextCtrl(panel, value=current_settings.get("celestrak_url", ""))
        sizer.Add(self.url_input, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        sizer.Add(wx.StaticText(panel, label="* Используйте {norad_id} в строке адреса как маску для ID."), 0,
                  wx.LEFT | wx.TOP, 10)

        # Кнопки ОК / Отмена
        btn_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(panel, wx.ID_OK, label="Сохранить")
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, label="Отмена")
        btn_sizer.AddButton(ok_btn)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()

        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 15)
        panel.SetSizer(sizer)


class OrbitControlFrame(wx.Frame):
    def __init__(self):
        super().__init__(parent=None, title="🚀 Phisics-Orbit-0.1: Баллистический комплекс", size=(1150, 750))
        self.load_settings()  # Загружаем настройки адресов

        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # ЛЕВАЯ ПАНЕЛЬ
        left_panel = wx.Panel(panel)
        left_sizer = wx.BoxSizer(wx.VERTICAL)

        # Мониторинг Солнца + Кнопка Настроек
        status_box = wx.StaticBox(left_panel, label="🛰 Системный мониторинг")
        status_sizer = wx.StaticBoxSizer(status_box, wx.HORIZONTAL)
        self.weather_label = wx.StaticText(left_panel,
                                           label="🟢 Магнитное поле спокойное (Kp = 1.0).\nПараметры атмосферы штатные.")
        self.weather_label.SetForegroundColour(wx.Colour(0, 128, 0))

        settings_btn = wx.Button(left_panel, label="⚙️", size=(35, 35))
        settings_btn.Bind(wx.EVT_BUTTON, self.on_open_settings)

        status_sizer.Add(self.weather_label, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        status_sizer.Add(settings_btn, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        left_sizer.Add(status_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.input_notebook = wx.Notebook(left_panel)

        # Вкладка А: Библиотека
        tab_json = wx.Panel(self.input_notebook)
        json_sizer = wx.BoxSizer(wx.VERTICAL)
        json_sizer.Add(wx.StaticText(tab_json, label="Выберите объект из базы:"), 0, wx.ALL, 5)
        self.sat_listbox = wx.ListBox(tab_json, style=wx.LB_SINGLE)
        self.sat_listbox.Bind(wx.EVT_LISTBOX, self.on_satellite_selected)  # Клик по списку
        json_sizer.Add(self.sat_listbox, 1, wx.EXPAND | wx.ALL, 5)

        norad_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.norad_input = wx.TextCtrl(tab_json)
        self.norad_input.SetHint("NORAD ID (напр. 37362)")
        norad_btn = wx.Button(tab_json, label="Скачать API")
        norad_btn.Bind(wx.EVT_BUTTON, self.on_add_norad_click)
        norad_sizer.Add(self.norad_input, 1, wx.EXPAND | wx.RIGHT, 5)
        norad_sizer.Add(norad_btn, 0, wx.EXPAND)
        json_sizer.Add(norad_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        tab_json.SetSizer(json_sizer)

        # Вкладка Б: Ввод TLE
        tab_tle = wx.Panel(self.input_notebook)
        tle_sizer = wx.BoxSizer(wx.VERTICAL)
        tle_sizer.Add(wx.StaticText(tab_tle, label="Редактирование строк TLE текущего ИСЗ:"), 0, wx.ALL, 5)
        self.tle_input = wx.TextCtrl(tab_tle, style=wx.TE_MULTILINE)
        tle_sizer.Add(self.tle_input, 1, wx.EXPAND | wx.ALL, 5)
        tab_tle.SetSizer(tle_sizer)

        # Вкладка В: Кеплеровские элементы
        tab_kep = wx.Panel(self.input_notebook)
        kep_grid = wx.FlexGridSizer(6, 2, 5, 5)
        kep_labels = ["Полуось a (км):", "Эксцентриситет e:", "Наклонение i (°):", "Узел Ω (°):", "Перицентр ω (°):",
                      "Аномалия M (°)"]
        self.kep_inputs = {}
        for label_text in kep_labels:
            lbl = wx.StaticText(tab_kep, label=label_text)
            txt = wx.TextCtrl(tab_kep, value="0.0")
            kep_grid.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL)
            kep_grid.Add(txt, 1, wx.EXPAND)
            self.kep_inputs[label_text] = txt
        kep_grid.AddGrowableCol(1, 1)
        tab_kep.SetSizer(kep_grid)

        self.input_notebook.AddPage(tab_json, "Библиотека")
        self.input_notebook.AddPage(tab_tle, "Ввод TLE")
        self.input_notebook.AddPage(tab_kep, "Кеплер")
        left_sizer.Add(self.input_notebook, 1, wx.EXPAND | wx.ALL, 10)

        # Кнопка ручного сохранения правок TLE / Кеплера в JSON базы данных!
        self.save_db_btn = wx.Button(left_panel, label="💾 СОХРАНИТЬ ПРАВКИ В БАЗУ ДАННЫХ")
        self.save_db_btn.Bind(wx.EVT_BUTTON, self.on_save_sat_data_to_json)
        left_sizer.Add(self.save_db_btn, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Блок времени
        time_box = wx.StaticBox(left_panel, label="📅 Баллистическое время и шаг")
        time_sizer = wx.StaticBoxSizer(time_box, wx.VERTICAL)
        self.date_picker = wx.adv.DatePickerCtrl(left_panel, style=wx.adv.DP_DROPDOWN)
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

        # ПРАВАЯ ПАНЕЛЬ
        self.right_notebook = wx.Notebook(panel)
        self.tab_graph = wx.Panel(self.right_notebook)
        graph_sizer = wx.BoxSizer(wx.VERTICAL)
        self.figure = Figure(figsize=(5, 4), dpi=100)
        self.axes = self.figure.add_subplot(111)
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

        self.export_btn = wx.Button(tab_table, label="📥 Экспортировать данные в CSV (Excel / OriginPro)")
        self.export_btn.Bind(wx.EVT_BUTTON, self.on_export_click)
        table_sizer.Add(self.export_btn, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
        tab_table.SetSizer(table_sizer)

        self.right_notebook.AddPage(self.tab_graph, "Графический анализ")
        self.right_notebook.AddPage(tab_table, "Таблица данных")

        main_sizer.Add(left_panel, 0, wx.EXPAND)
        main_sizer.Add(self.right_notebook, 1, wx.EXPAND | wx.ALL, 5)
        panel.SetSizer(main_sizer)
        self.load_satellites_from_json()
        self.Show()

    def load_settings(self):
        """Загрузка конфигурации из файла config.json"""
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                self.settings = json.load(f)
        else:
            self.settings = DEFAULT_SETTINGS.copy()

    def on_open_settings(self, event):
        """Открытие окна изменения URL-адреса Celestrak"""
        dlg = SettingsDialog(self, self.settings)
        if dlg.ShowModal() == wx.ID_OK:
            self.settings["celestrak_url"] = dlg.url_input.GetValue().strip()
            config_path = os.path.join(os.path.dirname(__file__), 'config.json')
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
            wx.MessageBox("Настройки успешно сохранены!", "Успех", wx.OK | wx.ICON_INFORMATION)
        dlg.Destroy()

    def load_satellites_from_json(self):
        self.sat_listbox.Clear()
        json_path = os.path.join(os.path.dirname(__file__), 'satellites.json')
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                self.sat_data = json.load(f)
                for norad_id, info in self.sat_data.items():
                    idx = self.sat_listbox.Append(f"{info['name']} (NORAD: {norad_id})")
                    self.sat_listbox.SetClientData(idx, info)
# 23
                if self.sat_listbox.GetCount() > 0:
                    self.sat_listbox.SetSelection(0)
                    self.on_satellite_selected(None)

    def on_satellite_selected(self, event):
        """Срабатывает при выборе ИСЗ в списке — раскидывает его TLE и Кеплера по вкладкам"""
        idx = self.sat_listbox.GetSelection()
        if idx == wx.NOT_FOUND: return
        info = self.sat_listbox.GetClientData(idx)

        # 1. Заполняем вкладку TLE
        self.tle_input.SetValue(f"{info.get('tle_l1', '')}\n{info.get('tle_l2', '')}")

        # 2. Если в базе есть готовая Кеплеровская строка (OMM), заполняем вкладку Кеплера
        if 'kepler' in info:
            kep = info['kepler']
            for label, key in [("Полуось a (км):", "a"), ("Эксцентриситет e:", "e"), ("Наклонение i (°):", "i"),
                               ("Узел Ω (°):", "omega"), ("Перицентр ω (°):", "w"), ("Аномалия M (°)", "M")]:
                if key in kep: self.kep_inputs[label].SetValue(str(kep[key]))

    def on_save_sat_data_to_json(self, event):
        """Ручное сохранение отредактированного TLE или Кеплера обратно в базу satellites.json"""
        idx = self.sat_listbox.GetSelection()
        if idx == wx.NOT_FOUND:
            wx.MessageBox("Спутник не выбран!", "Внимание", wx.OK | wx.ICON_WARNING)
            return

        info = self.sat_listbox.GetClientData(idx)
        json_path = os.path.join(os.path.dirname(__file__), 'satellites.json')

        # Читаем то, что пользователь изменил во вкладках прямо сейчас
        lines = self.tle_input.GetValue().strip().split('\n')
        if len(lines) >= 2:
            info['tle_l1'] = lines[0].strip()
            info['tle_l2'] = lines[1].strip()

        # Забираем данные из полей Кеплера
        info['kepler'] = {
            "a": float(self.kep_inputs["Полуось a (км):"].GetValue()),
            "e": float(self.kep_inputs["Эксцентриситет e:"].GetValue()),
            "i": float(self.kep_inputs["Наклонение i (°):"].GetValue()),
            "omega": float(self.kep_inputs["Узел Ω (°):"].GetValue()),
            "w": float(self.kep_inputs["Перицентр ω (°):"].GetValue()),
            "M": float(self.kep_inputs["Аномалия M (°)"].GetValue())
        }

        # Находим и перезаписываем в корневом словаре базы данных
        for norad_id, data in self.sat_data.items():
            if data['name'] == info['name']:
                self.sat_data[norad_id] = info
                break

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(self.sat_data, f, ensure_ascii=False, indent=2)

        wx.MessageBox(f"Данные для '{info['name']}' успешно обновлены в файле satellites.json!", "Успех сохранения",
                      wx.OK | wx.ICON_INFORMATION)

    def on_add_norad_click(self, event):
        """Улучшенный обработчик: качает с API или создает карточку для ручного ввода"""
        norad_id = self.norad_input.GetValue().strip()
        if not norad_id.isdigit():
            wx.MessageBox("Введите числовой NORAD ID!", "Ошибка", wx.OK | wx.ICON_ERROR)
            return

        # 1. Пробуем скачать данные автоматически с Celestrak
        name = download_tle_from_celestrak(norad_id)

        if name:
            # Если скачалось — обновляем список и выводим успех
            self.load_satellites_from_json()
            self.norad_input.SetValue("")
            wx.MessageBox(f"Объект {name} успешно добавлен в базу!", "Успех API", wx.OK | wx.ICON_INFORMATION)
        else:
            # 2. Если интернет упал или спутника нет на Celestrak — создаем пустую карточку!
            msg = f"Не удалось получить TLE с Celestrak автоматически.\n\nСоздать карточку объекта NORAD {norad_id} для ручного ввода данных?"
            dlg = wx.MessageDialog(self, msg, "Автономный режим базы данных", wx.YES_NO | wx.ICON_QUESTION)

            if dlg.ShowModal() == wx.ID_YES:
                json_path = os.path.join(os.path.dirname(__file__), 'satellites.json')
                sat_data = {}

                # Читаем текущую базу
                if os.path.exists(json_path):
                    with open(json_path, 'r', encoding='utf-8') as f:
                        try:
                            sat_data = json.load(f)
                        except:
                            sat_data = {}

                # Записываем пустую болванку под ручной ввод
                sat_data[str(norad_id)] = {
                    "name": f"Ручной ввод (NORAD: {norad_id})",
                    "tle_l1": f"1 {norad_id}U 26001A   26141.50000000  .00000000  00000-0  00000-0 0  9991",
                    "tle_l2": f"2 {norad_id}  00.0000  00.0000 0000000  00.0000  00.0000 15.00000000000000",
                    "kepler": {"a": 6771.0, "e": 0.0, "i": 0.0, "omega": 0.0, "w": 0.0, "M": 0.0}
                }

                # Сохраняем в файл
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(sat_data, f, ensure_ascii=False, indent=2)

                # Перезагружаем интерфейс
                self.load_satellites_from_json()
                self.norad_input.SetValue("")

                # Автоматически пролистываем список на самый конец к новому спутнику
                last_idx = self.sat_listbox.GetCount() - 1
                self.sat_listbox.SetSelection(last_idx)
                self.on_satellite_selected(None)

                wx.MessageBox(
                    "Карточка создана! Введите TLE или Кеплеровы элементы во вкладках и нажмите 'Сохранить правки в базу'.",
                    "Инфо", wx.OK | wx.ICON_INFORMATION)
            dlg.Destroy()

    def on_export_click(self, event):
        if self.grid.GetNumberRows() == 0: return
        with wx.FileDialog(self, "Сохранить баллистические данные", wildcard="CSV файлы (*.csv)|*.csv",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dlg:
            if dlg.ShowModal() == wx.ID_CANCEL: return
            if save_grid_to_csv(dlg.GetPath(), self.grid):
                wx.MessageBox("Данные успешно экспортированы!", "Успех", wx.OK | wx.ICON_INFORMATION)

    def on_run_simulation(self, event):
        selected_tab = self.input_notebook.GetSelection()
        step_sec = int(self.step_input.GetValue()) if self.step_input.GetValue().isdigit() else 120

        tle_l1, tle_l2 = "", ""

        if selected_tab == 0 or selected_tab == 1:  # Работаем по TLE (из базы или вручную из вкладки)
            lines = self.tle_input.GetValue().strip().split('\n')
            if len(lines) < 2:
                wx.MessageBox("Недостаточно строк TLE в поле редактирования!", "Ошибка", wx.OK | wx.ICON_ERROR)
                return
            tle_l1, tle_l2 = lines[0].strip(), lines[1].strip()

            try:
                orbit_points = get_points_along_orbit(tle_l1, tle_l2, datetime.utcnow(), 45, step_sec)
            except Exception as e:
                wx.MessageBox(f"Ошибка SGP4: {e}")
                return

        elif selected_tab == 2:  # Кеплеровский аналитический расчет
            try:
                a = float(self.kep_inputs["Полуось a (км):"].GetValue())
                e = float(self.kep_inputs["Эксцентриситет e:"].GetValue())
                i = float(self.kep_inputs["Наклонение i (°):"].GetValue())
                omega = float(self.kep_inputs["Узел Ω (°):"].GetValue())
                w = float(self.kep_inputs["Перицентр ω (°):"].GetValue())
                M = float(self.kep_inputs["Аномалия M (°)"].GetValue())

                from kepler_converter import kepler_to_cartesian
                pos, vel = kepler_to_cartesian(a, e, i, omega, w, M)

                orbit_points = []
                import math
                for step_idx in range(int(45 * 60 / step_sec)):
                    nu_step = math.radians(M) + (step_idx * step_sec * 0.00111)
                    r_step = a * (1.0 - e * math.cos(nu_step))
                    lat_step = i * math.sin(nu_step)
                    lon_step = (omega + math.degrees(nu_step)) % 360.0
                    if lon_step > 180: lon_step -= 360.0

                    from datetime import timedelta
                    sim_time = datetime.utcnow() + timedelta(seconds=step_idx * step_sec)
                    orbit_points.append(
                        {'time': sim_time.strftime("%H:%M:%S"), 'height': r_step - 6371.0, 'lat': lat_step,
                         'lon': lon_step})
            except Exception as ex:
                wx.MessageBox(f"Ошибка Кеплера: {ex}")
                return

        if self.grid.GetNumberRows() > 0: self.grid.DeleteRows(0, self.grid.GetNumberRows())
        self.axes.clear()
        x_time, y_density = [], []

        for i, pt in enumerate(orbit_points):
            density = 0.0 if pt['height'] > 1500.0 else calculate_density(pt['height'], 150.0, 150.0, 1.0, 140.0)
            x_time.append(i * step_sec)
            y_density.append(density)

            self.grid.AppendRows(1)
            row = self.grid.GetNumberRows() - 1
            self.grid.SetCellValue(row, 0, pt['time'])
            self.grid.SetCellValue(row, 1, f"{pt['height']:.2f}")
            self.grid.SetCellValue(row, 2, f"{pt['lat']:.2f}")
            self.grid.SetCellValue(row, 3, f"{pt['lon']:.2f}")
            self.grid.SetCellValue(row, 4, f"{density:.4e}")

        self.axes.plot(x_time, y_density, color='#0284c7', linewidth=2)
        self.axes.set_title("Профиль плотности атмосферы")
        self.axes.set_xlabel("Время полета (сек)")
        self.axes.set_ylabel("Плотность, кг/м³")
        self.axes.grid(True)
        self.canvas.draw()
        wx.Bell()


if __name__ == "__main__":
    app = wx.App()
    frame = OrbitControlFrame()
    app.MainLoop()
# end