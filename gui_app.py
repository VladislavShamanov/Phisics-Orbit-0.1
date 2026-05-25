# gui_app.py
import wx
import wx.adv
import wx.grid
import json
import os
import math
from datetime import datetime, timedelta

import matplotlib

matplotlib.use('WXAgg')
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from matplotlib.figure import Figure

from orbit_propagator import save_grid_to_csv
from gost_model import calculate_density
from kepler_converter import kepler_to_cartesian, parse_omm_csv_string


class OrbitControlFrame(wx.Frame):
    def __init__(self):
        super().__init__(parent=None, title="🚀 Phisics-Orbit-0.1: Баллистический комплекс Сценариев", size=(1180, 780))

        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # ЛЕВАЯ ПАНЕЛЬ
        left_panel = wx.Panel(panel)
        left_sizer = wx.BoxSizer(wx.VERTICAL)

        # Блок выбора объекта с Группировкой (TreeCtrl вместо ListBox)
        left_sizer.Add(wx.StaticText(left_panel, label="📁 Библиотека ИСЗ и Групп:"), 0, wx.LEFT | wx.TOP, 5)
        self.sat_tree = wx.TreeCtrl(left_panel, style=wx.TR_HAS_BUTTONS | wx.TR_SINGLE)
        self.sat_tree.Bind(wx.EVT_TREE_SEL_CHANGED, self.on_tree_selection_changed)
        left_sizer.Add(self.sat_tree, 1, wx.EXPAND | wx.ALL, 5)

        self.input_notebook = wx.Notebook(left_panel)
        # ДОБАВИТЬ ЭТУ СТРОКУ: отслеживаем переключение вкладок!
        self.input_notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.on_tab_changed)


        # Вкладка А: Параметры Кеплера и Название Сценария
        tab_kep = wx.Panel(self.input_notebook)
        kep_grid = wx.FlexGridSizer(8, 2, 4, 4)

        # Поле для кастомного имени вымышленной орбиты
        kep_grid.Add(wx.StaticText(tab_kep, label="Имя сценария:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.scen_name_input = wx.TextCtrl(tab_kep, value="Симуляция - 01")
        kep_grid.Add(self.scen_name_input, 1, wx.EXPAND)

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

        # Вкладка Б: Импорт OMM CSV
        tab_csv = wx.Panel(self.input_notebook)
        csv_sizer = wx.BoxSizer(wx.VERTICAL)
        csv_sizer.Add(wx.StaticText(tab_csv, label="Вставьте шапку OMM CSV:"), 0, wx.ALL, 2)
        self.csv_hdr_input = wx.TextCtrl(tab_csv,
                                         value="OBJECT_NAME,OBJECT_ID,EPOCH,MEAN_MOTION,ECCENTRICITY,INCLINATION,RA_OF_ASC_NODE,ARG_OF_PERICENTER,MEAN_ANOMALY,NORAD_CAT_ID")
        csv_sizer.Add(self.csv_hdr_input, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 2)
        csv_sizer.Add(wx.StaticText(tab_csv, label="Вставьте строку данных спутника:"), 0, wx.ALL, 2)
        self.csv_data_input = wx.TextCtrl(tab_csv, style=wx.TE_MULTILINE, value="")
        csv_sizer.Add(self.csv_data_input, 1, wx.EXPAND | wx.ALL, 2)
        import_btn = wx.Button(tab_csv, label="⚡ ИМПОРТИРОВАТЬ СТРОКУ CSV В БАЗУ")
        import_btn.Bind(wx.EVT_BUTTON, self.on_import_omm_csv_click)
        csv_sizer.Add(import_btn, 0, wx.EXPAND | wx.ALL, 2)
        tab_csv.SetSizer(csv_sizer)

        self.input_notebook.AddPage(tab_kep, "Параметры Кеплера")
        self.input_notebook.AddPage(tab_csv, "Импорт OMM CSV")
        left_sizer.Add(self.input_notebook, 1, wx.EXPAND | wx.ALL, 5)

        # Кнопка сохранения правок
        self.save_db_btn = wx.Button(left_panel, label="💾 СОХРАНИТЬ ОРБИТУ В БАЗУ ДАННЫХ")
        self.save_db_btn.Bind(wx.EVT_BUTTON, self.on_save_scenario_to_json)
        left_sizer.Add(self.save_db_btn, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        # Блок Времени и Длительности Симуляции
        time_box = wx.StaticBox(left_panel, label="📅 Управление временем расчета")
        time_sizer = wx.StaticBoxSizer(time_box, wx.VERTICAL)

        # Выбор Даты и Времени
        dt_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.date_picker = wx.adv.DatePickerCtrl(left_panel, style=wx.adv.DP_DROPDOWN)
        self.time_picker = wx.adv.TimePickerCtrl(left_panel)
        dt_sizer.Add(self.date_picker, 1, wx.EXPAND | wx.RIGHT, 5)
        dt_sizer.Add(self.time_picker, 1, wx.EXPAND)
        time_sizer.Add(wx.StaticText(left_panel, label="Дата и время старта симуляции:"), 0, wx.LEFT, 2)
        time_sizer.Add(dt_sizer, 0, wx.EXPAND | wx.ALL, 2)

        # Длительность и Шаг симуляции
        sim_param_grid = wx.FlexGridSizer(2, 2, 5, 5)
        sim_param_grid.Add(wx.StaticText(left_panel, label="Длительность (мин):"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.duration_input = wx.TextCtrl(left_panel, value="90")  # По умолчанию 1 виток ~ 90 мин
        sim_param_grid.Add(self.duration_input, 1, wx.EXPAND)

        sim_param_grid.Add(wx.StaticText(left_panel, label="Шаг расчета (сек):"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.step_input = wx.TextCtrl(left_panel, value="120")
        sim_param_grid.Add(self.step_input, 1, wx.EXPAND)
        sim_param_grid.AddGrowableCol(1, 1)
        time_sizer.Add(sim_param_grid, 0, wx.EXPAND | wx.ALL, 2)

        left_sizer.Add(time_sizer, 0, wx.EXPAND | wx.ALL, 5)

        self.run_btn = wx.Button(left_panel, label="🚀 ЗАПУСТИТЬ МОДЕЛИРОВАНИЕ")
        self.run_btn.SetBackgroundColour(wx.Colour(2, 132, 199))
        self.run_btn.SetForegroundColour(wx.WHITE)
        self.run_btn.Bind(wx.EVT_BUTTON, self.on_run_simulation)
        left_sizer.Add(self.run_btn, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        left_panel.SetSizer(left_sizer)

        # ПРАВАЯ ПАНЕЛЬ (Результаты)
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

        self.export_btn = wx.Button(tab_table, label="📥 Экспортировать данные в CSV")
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

    def on_tab_changed(self, event):
        """Скрывает или показывает кнопку сохранения базы в зависимости от активной вкладки"""
        selected_tab = self.input_notebook.GetSelection()

        # Индекс 0 — это вкладка "Параметры Кеплера"
        if selected_tab == 0:
            self.save_db_btn.Show()  # Показываем кнопку
        else:
            self.save_db_btn.Hide()  # Скрываем кнопку

        # КРИТИЧЕСКИ ВАЖНО для wxPython: принудительно пересчитываем геометрию интерфейса,
        # чтобы освободившееся место красиво заполнилось другими элементами
        self.GetSizer().Layout()

        event.Skip()  # Позволяем wxPython завершить стандартную смену вкладки

    def load_satellites_from_json(self):
        """Загрузка базы данных с распределением по Группам и Эпохам в дерево TreeCtrl"""
        self.sat_tree.DeleteAllItems()
        self.tree_root = self.sat_tree.AddRoot("Космические объекты")

        json_path = os.path.join(os.path.dirname(__file__), 'satellites.json')
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                self.sat_data = json.load(f)

                # Собираем уникальные группы
                groups = {}
                for norad_id, info in self.sat_data.items():
                    g_name = info.get("group", "Вымышленные / Кастомные")
                    if g_name not in groups:
                        groups[g_name] = self.sat_tree.AppendItem(self.tree_root, g_name)

                    # Добавляем спутник в соответствующую ветку группы
                    sat_item = self.sat_tree.AppendItem(groups[g_name], info['name'])

                    # Добавляем эпохи внутрь спутника
                    if 'history' in info:
                        for ep in info['history']:
                            ep_name = f"Сценарий: {ep.get('comment', 'Без имени')}"
                            ep_item = self.sat_tree.AppendItem(sat_item, ep_name)
                            # Привязываем данные эпохи к конечному узлу дерева!
                            self.sat_tree.SetItemData(ep_item, ep)

        self.sat_tree.Expand(self.tree_root)

    def on_tree_selection_changed(self, event):
        """Срабатывает при клике на узел дерева — вытаскивает Кеплеровы элементы выбранного сценария"""
        item = event.GetItem()
        if not item.IsOk() or item == self.tree_root: return

        ep = self.sat_tree.GetItemData(item)
        # Если данные привязаны (это узел конкретной эпохи) — раскидываем по полям
        if ep:
            self.scen_name_input.SetValue(str(ep.get('comment', 'Симуляция - 01')))
            self.kep_inputs["Полуось a (км):"].SetValue(str(ep['a']))
            self.kep_inputs["Эксцентриситет e:"].SetValue(str(ep['e']))
            self.kep_inputs["Наклонение i (°):"].SetValue(str(ep['i']))
            self.kep_inputs["Узел Ω (°):"].SetValue(str(ep['omega']))
            self.kep_inputs["Перицентр ω (°):"].SetValue(str(ep['w']))
            self.kep_inputs["Аномалия M (°)"].SetValue(str(ep['M']))

    def on_import_omm_csv_click(self, event):
        """Парсит OMM CSV строку с сайта и автоматически определяет её в группу кубсатов"""
        hdr = self.csv_hdr_input.GetValue().strip()
        data_line = self.csv_data_input.GetValue().strip().split('\n')[-1]

        res = parse_omm_csv_string(hdr, data_line)
        if res is None:
            wx.MessageBox("Ошибка парсинга CSV!", "Ошибка", wx.OK | wx.ICON_ERROR)
            return

        json_path = os.path.join(os.path.dirname(__file__), 'satellites.json')
        norad_str = str(res['norad_id'])

        if norad_str not in self.sat_data:
            self.sat_data[norad_str] = {"name": res['name'], "group": "Импортированные кубсаты", "history": []}

        new_epoch = {
            "epoch": res['epoch'],
            "comment": f"Импорт за {res['epoch'][:10]}",
            "a": res['a'], "e": res['e'], "i": res['i'],
            "omega": res['omega'], "w": res['w'], "M": res['M']
        }
        self.sat_data[norad_str]['history'].append(new_epoch)

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(self.sat_data, f, ensure_ascii=False, indent=2)

        self.load_satellites_from_json()
        wx.MessageBox("Сценарий импортирован и добавлен в группу!", "Успех", wx.OK | wx.ICON_INFORMATION)

    def on_save_scenario_to_json(self, event):
        """Сохраняет текущую кастомную орбиту под именем из поля ввода в группу 'Вымышленные'"""
        scen_name = self.scen_name_input.GetValue().strip()

        # Создаем или обновляем виртуальный ИСЗ в базе для вымышленных орбит
        fict_id = "CUSTOM_ORBITS"
        if fict_id not in self.sat_data:
            self.sat_data[fict_id] = {"name": "Кастомные симуляции", "group": "Вымышленные / Кастомные",
                                      "history": []}

        new_ep = {
            "epoch": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
            "comment": scen_name,
            "a": float(self.kep_inputs["Полуось a (км):"].GetValue()),
            "e": float(self.kep_inputs["Эксцентриситет e:"].GetValue()),
            "i": float(self.kep_inputs["Наклонение i (°):"].GetValue()),
            "omega": float(self.kep_inputs["Узел Ω (°):"].GetValue()),
            "w": float(self.kep_inputs["Перицентр ω (°):"].GetValue()),
            "M": float(self.kep_inputs["Аномалия M (°)"].GetValue())
        }

        self.sat_data[fict_id]['history'].append(new_ep)

        json_path = os.path.join(os.path.dirname(__file__), 'satellites.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(self.sat_data, f, ensure_ascii=False, indent=2)

        self.load_satellites_from_json()
        wx.MessageBox(f"Сценарий '{scen_name}' сохранен в группу кастомных орбит!", "Успех",
                      wx.OK | wx.ICON_INFORMATION)

    def on_export_click(self, event):
        if self.grid.GetNumberRows() == 0: return
        with wx.FileDialog(self, "Сохранить данные", wildcard="CSV файлы (*.csv)|*.csv",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dlg:
            if dlg.ShowModal() == wx.ID_CANCEL: return
            if save_grid_to_csv(dlg.GetPath(), self.grid):
                wx.MessageBox("Экспорт завершен успешно!", "Успех")

    def on_run_simulation(self, event):
        # Читаем шаг расчета и длительность
        try:
            step_sec = int(self.step_input.GetValue())
        except:
            step_sec = 120
        try:
            duration_min = int(self.duration_input.GetValue())
        except:
            duration_min = 90

        # Собираем время старта из нативных виджетов даты и времени!
        wx_date = self.date_picker.GetValue()
        wx_time = self.time_picker.GetValue()
        start_time = datetime(wx_date.GetYear(), wx_date.GetMonth() + 1, wx_date.GetDay(),
                              wx_time.GetHour(), wx_time.GetMinute(), wx_time.GetSecond())

        try:
            a = float(self.kep_inputs["Полуось a (км):"].GetValue())
            e = float(self.kep_inputs["Эксцентриситет e:"].GetValue())
            i = float(self.kep_inputs["Наклонение i (°):"].GetValue())
            omega = float(self.kep_inputs["Узел Ω (°):"].GetValue())
            w = float(self.kep_inputs["Перицентр ω (°):"].GetValue())
            M = float(self.kep_inputs["Аномалия M (°)"].GetValue())

            pos, vel = kepler_to_cartesian(a, e, i, omega, w, M)

            orbit_points = []
            # Считаем ровно столько минут, сколько ввел пользователь!
            for step_idx in range(int(duration_min * 60 / step_sec)):
                nu_step = math.radians(M) + (step_idx * step_sec * 0.00111)
                r_step = a * (1.0 - e * math.cos(nu_step))
                lat_step = i * math.sin(nu_step)
                lon_step = (omega + math.degrees(nu_step)) % 360.0
                if lon_step > 180: lon_step -= 360.0

                sim_time = start_time + timedelta(seconds=step_idx * step_sec)
                orbit_points.append(
                    {'time': sim_time.strftime("%H:%M:%S"), 'height': r_step - 6371.0, 'lat': lat_step,
                     'lon': lon_step})
        except Exception as ex:
            wx.MessageBox(f"Ошибка параметров баллистики: {ex}")
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
        self.axes.set_title(f"Профиль плотности атмосферы (Сценарий: {self.scen_name_input.GetValue()})")
        self.axes.set_xlabel("Время полета (сек)")
        self.axes.set_ylabel("Плотность, кг/м³")
        self.axes.grid(True)
        self.canvas.draw()
        wx.Bell()

if __name__ == "__main__":
    app = wx.App()
    frame = OrbitControlFrame()
    app.MainLoop()

