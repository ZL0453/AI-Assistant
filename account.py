# account.py 开头部分
from kivy.config import Config
Config.set('graphics', 'width', '400')
Config.set('graphics', 'height', '712')
Config.set('graphics', 'resizable', False)

import sqlite3
from datetime import datetime, timedelta
import os
from collections import OrderedDict
import csv
import json

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.video import Video
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen
from kivy.core.window import Window
from kivy.core.text import LabelBase
from kivy.lang import Builder          # 新增导入
from ai_state import AIState

# 加载对应的 kv 文件
Builder.load_file('accounting.kv')     # 新增加载
from kivy.config import Config
Config.set('kivy', 'keyboard_mode', 'system')

# ---------- 修复中文显示（优先使用楷体） ----------
def register_chinese_font():
    windows_dir = os.environ.get('WINDIR', 'C:/Windows')
    font_dir = os.path.join(windows_dir, 'Fonts')
    candidates = [
        'simkai.ttf',   # 楷体
        'KaiTi.ttf',    # 楷体备用
        'msyh.ttc',     # 微软雅黑
        'simhei.ttf',   # 黑体
        'simsun.ttc',   # 宋体
    ]
    for font_name in candidates:
        font_path = os.path.join(font_dir, font_name)
        if os.path.exists(font_path):
            LabelBase.register(name='Chinese', fn_regular=font_path)
            Label.font_name = 'Chinese'
            print(f"已加载中文字体：{font_path}")
            return True
    print("警告：未找到中文字体，中文可能无法正常显示")
    return False

register_chinese_font()
# ---------------------------------

def init_db():
    conn = sqlite3.connect('accounting.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            date TEXT NOT NULL,
            type TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            month TEXT PRIMARY KEY,
            generated_at TEXT
        )
    ''')
    conn.commit()
    return conn

class AccountingRoot(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.message_rules = self.load_message_rules()
        self.conn = init_db()
        self.load_records()
        self.update_statistics()
        self.update_background()
        self.ids.date_input.text = datetime.now().strftime('%Y-%m-%d')
        self.check_monthly_reminder()
        self.import_data(silent=True)

        # 新增：绑定类型 Spinner 的 text 变化
        self.ids.type_spinner.bind(text=self.on_type_change)
        # 初始更新一次分类列表
        self.on_type_change(self.ids.type_spinner, self.ids.type_spinner.text)

    def on_type_change(self, spinner, text):
        """当类型在收入/支出之间切换时，更新分类 Spinner 的 values"""
        if text == '收入':
            self.ids.category_spinner.values = ['工资', '奖金', '理财']
        else:
            self.ids.category_spinner.values = ['餐饮', '交通', '购物', '娱乐', '住房', '医疗', '其他']
        # 若当前选中项不在新列表中，则自动设为第一项
        if self.ids.category_spinner.text not in self.ids.category_spinner.values:
            self.ids.category_spinner.text = self.ids.category_spinner.values[0]
        self.update_background(text)
    
    def is_daytime(self):
        hour = datetime.now().hour
        return 6 <= hour < 18

    def update_background(self, record_type=None):
        if record_type is None:
            record_type = '支出'
        prefix = 'income' if record_type == '收入' else 'expense'
        suffix = 'day' if self.is_daytime() else 'night'
        video_file = f"{prefix}_{suffix}.mp4"
        video_path = os.path.join(os.getcwd(), video_file)
        if os.path.exists(video_path):
            self.ids.bg_video.source = video_path
            self.ids.bg_video.state = 'play'
            self.ids.bg_video.volume = 0      # 新增：静音
            print(f"切换背景视频：{video_file}")
        else:
            print(f"警告：视频文件不存在 {video_path}，背景将保持纯色。")
            self.ids.bg_video.source = ''

    def add_record(self):
        amount_text = self.ids.amount_input.text.strip()
        if not amount_text:
            return
        try:
            amount = float(amount_text)
        except ValueError:
            self.ids.amount_input.text = ''
            return

        category = self.ids.category_spinner.text
        description = self.ids.desc_input.text.strip()
        date = self.ids.date_input.text.strip() or datetime.now().strftime('%Y-%m-%d')
        record_type = self.ids.type_spinner.text

        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO records (amount, category, description, date, type)
            VALUES (?, ?, ?, ?, ?)
        ''', (amount, category, description, date, record_type))
        self.conn.commit()
        # 新增：更新AI状态（记账节律）
        ai_state = AIState()
        ai_state.record_account_activity()
        # 立即导出备份
        self.export_data(silent=True)

        # 新增：显示特殊文本
        self.show_special_message(amount, category, record_type)

        # 清空输入，日期重置为今天
        self.ids.amount_input.text = ''
        self.ids.desc_input.text = ''
        self.ids.date_input.text = datetime.now().strftime('%Y-%m-%d')

        self.load_records()
        self.update_statistics()
        self.update_background(record_type)

    def delete_record(self, record_id):
        """删除指定ID的记录，并刷新界面"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM records WHERE id=?", (record_id,))
        self.conn.commit()
        # 立即导出备份
        self.export_data(silent=True)
        self.load_records()
        self.update_statistics()

    def update_record(self, record_id, amount, category, description, date, record_type):
        """更新指定ID的记录"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE records
            SET amount=?, category=?, description=?, date=?, type=?
            WHERE id=?
        ''', (amount, category, description, date, record_type, record_id))
        self.conn.commit()
        # 立即导出备份
        self.export_data(silent=True)
        self.load_records()
        self.update_statistics()

    def load_records(self):
        """从数据库加载所有记录，按月份->日期两级分组显示，每条记录可点击编辑"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM records ORDER BY date DESC, id DESC')
        records = cursor.fetchall()

        records_list = self.ids.records_list
        records_list.clear_widgets()

        months = OrderedDict()
        for record in records:
            record_id, amount, category, description, date, record_type = record
            month = date[:7] if len(date) >= 7 else '未知月份'
            day = date if len(date) >= 10 else '未知日期'
            if month not in months:
                months[month] = OrderedDict()
            if day not in months[month]:
                months[month][day] = []
            months[month][day].append(record)

        for month, days in months.items():
            month_btn = Button(
                text=month,
                size_hint_y=None,
                height=40,
                background_normal='',
                background_color=(0, 0, 0, 0.5),
                color=(1, 1, 1, 1),
                font_name='Chinese'
            )

            month_content = GridLayout(
                cols=1,
                size_hint_y=None,
                spacing=0
            )
            month_content.bind(minimum_height=month_content.setter('height'))
            month_content.collapsed = False

            for day, day_records in days.items():
                day_btn = Button(
                    text=day,
                    size_hint_y=None,
                    height=30,
                    background_normal='',
                    background_color=(0.2, 0.2, 0.2, 0.5),
                    color=(1, 1, 1, 1),
                    font_name='Chinese'
                )

                day_records_grid = GridLayout(
                    cols=1,
                    size_hint_y=None,
                    spacing=2
                )
                day_records_grid.bind(minimum_height=day_records_grid.setter('height'))
                day_records_grid.collapsed = False

                # 添加记录行（可点击的按钮）
                for rec in day_records:
                    record_id, amount, category, description, date, record_type = rec
                    sign = '+' if record_type == '收入' else '-'
                    text = f"{sign}{amount:.2f} | {category} | {description}"

                    # 使用按钮模拟整行，点击打开编辑弹窗
                    record_btn = Button(
                        text=text,
                        size_hint_y=None,
                        height=30,
                        background_normal='',
                        background_color=(0, 0, 0, 0),  # 完全透明
                        color=(0.2, 0.6, 0.2, 1) if record_type == '收入' else (0.8, 0.2, 0.2, 1),
                        font_name='Chinese',
                        halign='left',
                        text_size=(None, 30),
                        valign='middle'
                    )
                    # 绑定点击事件，使用 lambda 捕获 record_id
                    record_btn.bind(on_release=lambda instance, rid=record_id: self.show_edit_popup(rid))
                    day_records_grid.add_widget(record_btn)

                def toggle_day(instance, grid=day_records_grid):
                    if grid.collapsed:
                        grid.height = grid.minimum_height
                        grid.opacity = 1
                        grid.collapsed = False
                    else:
                        grid.height = 0
                        grid.opacity = 0
                        grid.collapsed = True

                day_btn.bind(on_release=toggle_day)

                day_group = GridLayout(
                    cols=1,
                    size_hint_y=None,
                    spacing=0
                )
                day_group.bind(minimum_height=day_group.setter('height'))
                day_group.add_widget(day_btn)
                day_group.add_widget(day_records_grid)

                month_content.add_widget(day_group)

            def toggle_month(instance, content=month_content):
                if content.collapsed:
                    content.height = content.minimum_height
                    content.opacity = 1
                    content.collapsed = False
                else:
                    content.height = 0
                    content.opacity = 0
                    content.collapsed = True

            month_btn.bind(on_release=toggle_month)

            month_group = GridLayout(
                cols=1,
                size_hint_y=None,
                spacing=0
            )
            month_group.bind(minimum_height=month_group.setter('height'))
            month_group.add_widget(month_btn)
            month_group.add_widget(month_content)

            records_list.add_widget(month_group)

    def show_edit_popup(self, record_id):
        """显示编辑记录弹窗，包含修改和删除功能"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM records WHERE id=?", (record_id,))
        record = cursor.fetchone()
        if not record:
            return

        _, amount_orig, category_orig, description_orig, date_orig, type_orig = record

        # 创建弹窗内容
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        scroll = ScrollView(size_hint=(1, None), size=(Window.width, Window.height * 0.6))
        form = GridLayout(cols=2, spacing=5, size_hint_y=None)
        form.bind(minimum_height=form.setter('height'))

        # 金额
        form.add_widget(Label(text="金额:", font_name='Chinese', color=(0,0,0,1), size_hint_y=None, height=40))
        amount_input = TextInput(text=str(amount_orig), multiline=False, font_name='Chinese', size_hint_y=None, height=40)
        form.add_widget(amount_input)

        # 类型
        form.add_widget(Label(text="类型:", font_name='Chinese', color=(0,0,0,1), size_hint_y=None, height=40))
        type_spinner = Spinner(text=type_orig, values=["收入", "支出"], font_name='Chinese', size_hint_y=None, height=40)
        form.add_widget(type_spinner)

        # 分类（根据初始类型设置 values）
        form.add_widget(Label(text="分类:", font_name='Chinese', color=(0,0,0,1), size_hint_y=None, height=40))
        if type_orig == '收入':
            category_values = ['工资', '奖金', '理财']
        else:
            category_values = ['餐饮', '交通', '购物', '娱乐', '住房', '医疗', '其他']
        category_spinner = Spinner(text=category_orig, values=category_values, font_name='Chinese', size_hint_y=None, height=40)
        form.add_widget(category_spinner)

        # 描述
        form.add_widget(Label(text="描述:", font_name='Chinese', color=(0,0,0,1), size_hint_y=None, height=40))
        desc_input = TextInput(text=description_orig or "", multiline=False, font_name='Chinese', size_hint_y=None, height=40)
        form.add_widget(desc_input)

        # 日期
        form.add_widget(Label(text="日期:", font_name='Chinese', color=(0,0,0,1), size_hint_y=None, height=40))
        date_input = TextInput(text=date_orig, multiline=False, font_name='Chinese', size_hint_y=None, height=40)
        form.add_widget(date_input)

        scroll.add_widget(form)
        content.add_widget(scroll)

        # 按钮行
        btn_box = BoxLayout(size_hint_y=None, height=50, spacing=10)

        save_btn = Button(
            text='保存修改',
            background_normal='',
            background_color=(0.2, 0.6, 0.2, 0.8),
            color=(1, 1, 1, 1),
            font_name='Chinese'
        )
        delete_btn = Button(
            text='删除',
            background_normal='',
            background_color=(0.8, 0.2, 0.2, 0.8),
            color=(1, 1, 1, 1),
            font_name='Chinese'
        )
        btn_box.add_widget(save_btn)
        btn_box.add_widget(delete_btn)
        content.add_widget(btn_box)

        popup = Popup(
            title='编辑记录',
            content=content,
            size_hint=(0.9, 0.8)
        )

        # 类型变更时更新分类列表
        def update_category_values(instance, text):
            if text == '收入':
                category_spinner.values = ['工资', '奖金', '理财']
            else:
                category_spinner.values = ['餐饮', '交通', '购物', '娱乐', '住房', '医疗', '其他']
            if category_spinner.text not in category_spinner.values:
                category_spinner.text = category_spinner.values[0]

        type_spinner.bind(text=update_category_values)

        def save_changes(instance):
            try:
                new_amount = float(amount_input.text.strip())
                if new_amount <= 0:
                    return
            except ValueError:
                return
            new_category = category_spinner.text
            new_description = desc_input.text.strip()
            new_date = date_input.text.strip() or date_orig
            new_type = type_spinner.text

            self.update_record(record_id, new_amount, new_category, new_description, new_date, new_type)
            popup.dismiss()

        def delete_and_close(instance):
            self.delete_record(record_id)
            popup.dismiss()

        save_btn.bind(on_release=save_changes)
        delete_btn.bind(on_release=delete_and_close)

        popup.open()

    def update_statistics(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT SUM(amount) FROM records WHERE type='收入'")
        total_income = cursor.fetchone()[0] or 0
        cursor.execute("SELECT SUM(amount) FROM records WHERE type='支出'")
        total_expense = cursor.fetchone()[0] or 0
        balance = total_income - total_expense

        self.ids.income_label.text = f"总收入: {total_income:.2f}"
        self.ids.expense_label.text = f"总支出: {total_expense:.2f}"
        self.ids.balance_label.text = f"结余: {balance:.2f}"

    def generate_report(self, month=None):
        if month is None:
            today = datetime.now()
            first_of_this_month = today.replace(day=1)
            last_month_date = first_of_this_month - timedelta(days=1)
            month = last_month_date.strftime('%Y-%m')

        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM records WHERE date LIKE ? ORDER BY date", (month + '%',))
        records = cursor.fetchall()

        total_income = sum(r[1] for r in records if r[5] == '收入')
        total_expense = sum(r[1] for r in records if r[5] == '支出')

        expense_categories = {}
        for r in records:
            if r[5] == '支出':
                cat = r[2]
                expense_categories[cat] = expense_categories.get(cat, 0) + r[1]

        report_text = f"===== {month} 财务报告 =====\n\n"
        report_text += f"总收入: {total_income:.2f}\n"
        report_text += f"总支出: {total_expense:.2f}\n"
        report_text += f"结余: {total_income - total_expense:.2f}\n\n"
        report_text += "支出分类统计:\n"
        if expense_categories:
            for cat, amt in expense_categories.items():
                report_text += f"  {cat}: {amt:.2f}\n"
        else:
            report_text += "  （无支出记录）\n"
        if not records:
            report_text += "\n（该月无任何记录）\n"

        # 导出 CSV
        csv_filename = f"report_{month}.csv"
        csv_path = os.path.join(os.getcwd(), csv_filename)
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['日期', '类型', '金额', '分类', '描述'])
            for r in records:
                writer.writerow([r[4], r[5], r[1], r[2], r[3]])

        report_text += f"\n\n明细已导出至：{csv_filename}"

        cursor.execute(
            "INSERT OR REPLACE INTO reports (month, generated_at) VALUES (?, ?)",
            (month, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        )
        self.conn.commit()

        self.show_report_popup(month, report_text)

    def export_data(self, silent=False):
        """将所有记录导出为 backup.json。若 silent=True 则只打印日志，不弹窗"""
        import json
        cursor = self.conn.cursor()
        cursor.execute("SELECT amount, category, description, date, type FROM records ORDER BY id")
        records = cursor.fetchall()
        data = []
        for r in records:
            data.append({
                'amount': r[0],
                'category': r[1],
                'description': r[2],
                'date': r[3],
                'type': r[4]
            })

        file_path = os.path.join(os.getcwd(), 'backup.json')
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            if not silent:
                msg = f"数据已导出至：\n{file_path}"
                self.show_info_popup("导出数据", msg)
            else:
                print(f"自动导出成功：{len(data)} 条记录 -> {file_path}")
        except Exception as e:
            if not silent:
                msg = f"导出失败：{e}"
                self.show_info_popup("导出数据", msg)
            else:
                print(f"自动导出失败：{e}")

    def import_data(self, silent=False):
        """从 backup.json 导入数据，覆盖当前所有记录。若 silent=True 则只打印日志，不弹窗"""
        import json
        file_path = os.path.join(os.getcwd(), 'backup.json')
        if not os.path.exists(file_path):
            if not silent:
                self.show_info_popup("导入数据", "未找到 backup.json 文件")
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM records")
            for item in data:
                cursor.execute('''
                    INSERT INTO records (amount, category, description, date, type)
                    VALUES (?, ?, ?, ?, ?)
                ''', (item['amount'], item['category'], item['description'], item['date'], item['type']))
            self.conn.commit()
            self.load_records()
            self.update_statistics()
            if not silent:
                msg = f"成功导入 {len(data)} 条记录"
                self.show_info_popup("导入数据", msg)
            else:
                print(f"自动导入成功：{len(data)} 条记录")
        except Exception as e:
            if not silent:
                self.show_info_popup("导入数据", f"导入失败：{e}")
            else:
                print(f"自动导入失败：{e}")

    def show_info_popup(self, title, message):
        """通用信息弹窗"""
        content = BoxLayout(orientation='vertical', padding=20, spacing=10)
        label = Label(
            text=message,
            font_name='Chinese',
            halign='center',
            valign='middle'
        )
        label.bind(size=label.setter('text_size'))
        content.add_widget(label)

        close_btn = Button(
            text='确定',
            size_hint_y=None,
            height=40,
            background_normal='',
            background_color=(0.2, 0.2, 0.8, 0.8),
            color=(1, 1, 1, 1),
            font_name='Chinese'
        )
        content.add_widget(close_btn)

        popup = Popup(title=title, content=content, size_hint=(0.8, 0.5))
        close_btn.bind(on_release=popup.dismiss)
        popup.open()

    def show_report_popup(self, month, report_text):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        scroll = ScrollView()
        label = Label(
            text=report_text,
            size_hint_y=None,
            halign='left',
            valign='top',
            font_name='Chinese'
        )
        label.bind(texture_size=label.setter('size'))
        scroll.add_widget(label)
        content.add_widget(scroll)

        close_btn = Button(
            text='关闭',
            size_hint_y=None,
            height=40,
            background_normal='',
            background_color=(0.2, 0.2, 0.8, 0.8),
            color=(1, 1, 1, 1),
            font_name='Chinese'
        )
        content.add_widget(close_btn)

        popup = Popup(
            title=f'{month} 财报',
            content=content,
            size_hint=(0.9, 0.8)
        )
        close_btn.bind(on_release=popup.dismiss)
        popup.open()

    def check_monthly_reminder(self):
        today = datetime.now()
        if today.day <= 5:
            first_of_this_month = today.replace(day=1)
            last_month_date = first_of_this_month - timedelta(days=1)
            month_key = last_month_date.strftime('%Y-%m')

            cursor = self.conn.cursor()
            cursor.execute("SELECT generated_at FROM reports WHERE month=?", (month_key,))
            if cursor.fetchone() is None:
                self.show_reminder_popup(month_key)

    def show_reminder_popup(self, month_key):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        msg = Label(
            text=f"您尚未生成 {month_key} 的财务报告。\n是否现在生成？",
            halign='center',
            font_name='Chinese'
        )
        content.add_widget(msg)

        btn_box = BoxLayout(size_hint_y=None, height=50, spacing=10)
        generate_btn = Button(
            text='生成财报',
            background_normal='',
            background_color=(0.2, 0.6, 0.2, 0.8),
            color=(1, 1, 1, 1),
            font_name='Chinese'
        )
        cancel_btn = Button(
            text='稍后再说',
            background_normal='',
            background_color=(0.6, 0.2, 0.2, 0.8),
            color=(1, 1, 1, 1),
            font_name='Chinese'
        )
        btn_box.add_widget(generate_btn)
        btn_box.add_widget(cancel_btn)
        content.add_widget(btn_box)

        popup = Popup(
            title='财报提醒',
            content=content,
            size_hint=(0.85, 0.5)
        )
        generate_btn.bind(on_release=lambda *args: (popup.dismiss(), self.generate_report(month_key)))
        cancel_btn.bind(on_release=popup.dismiss)
        popup.open()

    def load_message_rules(self):
        """
        从外置 messages.json 文件加载消息规则。
        返回规则列表，每个规则为字典，包含 type, category, min_amount, max_amount, message 字段。
        """
        rules = []
        file_path = os.path.join(os.getcwd(), 'messages.json')
        if os.path.exists(file_path):
            try:
                import json
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    rules = data.get('rules', [])
            except Exception as e:
                print(f"加载消息规则失败：{e}")
        return rules

    def get_special_message(self, amount, category, record_type):
        """
        根据金额、分类、类型查找匹配的规则，返回特殊文本。
        匹配条件：type 相同，category 相同，金额在 [min_amount, max_amount) 区间内。
        """
        for rule in self.message_rules:
            if rule.get('type') != record_type:
                continue
            if rule.get('category') != category:
                continue
            min_amt = rule.get('min_amount', 0)
            max_amt = rule.get('max_amount', None)
            if amount < min_amt:
                continue
            if max_amt is not None and amount >= max_amt:
                continue
            return rule.get('message', '')
        return '记录成功！'

    def show_special_message(self, amount, category, record_type):
        """弹出显示特殊文本的 Popup"""
        msg = self.get_special_message(amount, category, record_type)
        content = BoxLayout(orientation='vertical', padding=20, spacing=10)
        label = Label(
            text=msg,
            font_name='Chinese',
            halign='center',
            valign='middle'
        )
        label.bind(size=label.setter('text_size'))
        content.add_widget(label)

        close_btn = Button(
            text='确定',
            size_hint_y=None,
            height=40,
            background_normal='',
            background_color=(0.2, 0.2, 0.8, 0.8),
            color=(1, 1, 1, 1),
            font_name='Chinese'
        )
        content.add_widget(close_btn)

        popup = Popup(
            title='提示',
            content=content,
            size_hint=(0.8, 0.4)
        )
        close_btn.bind(on_release=popup.dismiss)
        popup.open()

    def go_to_main(self, *args):
        app = App.get_running_app()
        if app:
            app.sm.current = 'main'
            
class AccountingScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.accounting_root = AccountingRoot()   # 保存引用
        self.add_widget(self.accounting_root)
        
"""
class AccountingApp(App):
    def build(self):
        self.sm = ScreenManager()
        self.sm.add_widget(MainMenuScreen(name='main'))
        self.sm.add_widget(AccountingScreen(name='accounting'))
        return self.sm

    def switch_to_accounting(self):
        self.sm.current = 'accounting'

    def switch_to_main(self):
        self.sm.current = 'main'

if __name__ == '__main__':
    AccountingApp().run()
"""