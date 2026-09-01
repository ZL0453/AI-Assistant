# health.py
from kivy.config import Config
Config.set('graphics', 'width', '400')
Config.set('graphics', 'height', '712')
Config.set('graphics', 'resizable', False)

import json
import os
from datetime import datetime
from collections import OrderedDict

from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.core.text import LabelBase
from kivy.lang import Builder
from ai_manager import AIManager
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.scrollview import ScrollView
from kivy.uix.video import Video
from datetime import datetime, timedelta
from kivy.core.window import Window
from ai_state import AIState
import re

# 注册中文字体
def register_font():
    windows_dir = os.environ.get('WINDIR', 'C:/Windows')
    font_dir = os.path.join(windows_dir, 'Fonts')
    candidates = ['simkai.ttf', 'KaiTi.ttf', 'msyh.ttc', 'simhei.ttf', 'simsun.ttc']
    for font_name in candidates:
        font_path = os.path.join(font_dir, font_name)
        if os.path.exists(font_path):
            LabelBase.register(name='Chinese', fn_regular=font_path)
            Label.font_name = 'Chinese'
            return
register_font()

from kivy.config import Config
Config.set('kivy', 'keyboard_mode', 'system')

Builder.load_file('health.kv')   # 加载 kv

class HealthRoot(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data = []
        self.profile = {}
        self.message_rules = self.load_message_rules()
        self.ai_manager = AIManager()
        self.load_data()
        self.ids.date_input.text = datetime.now().strftime('%Y-%m-%d')
        self.refresh_list()
        self.update_background()

    def is_daytime(self):
        """判断当前是否为白天（6:00-18:00）"""
        hour = datetime.now().hour
        return 6 <= hour < 18

    def update_background(self):
        """根据当前时间切换背景视频（health_day.mp4 或 health_night.mp4）"""
        video_file = 'health_day.mp4' if self.is_daytime() else 'health_night.mp4'
        video_path = os.path.join(os.getcwd(), video_file)
        if os.path.exists(video_path):
            self.ids.bg_video.source = video_path
            self.ids.bg_video.state = 'play'
            self.ids.bg_video.volume = 0   # 静音
            print(f"切换健康管理背景视频：{video_file}")
        else:
            print(f"警告：视频文件不存在 {video_path}，背景将保持纯色。")
            self.ids.bg_video.source = ''
            
    def load_data(self):
        file_path = os.path.join(os.getcwd(), 'health_backup.json')
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = json.load(f)
                    if isinstance(content, dict):
                        self.profile = content.get('profile', {})
                        self.data = content.get('records', [])
                    else:  # 旧版本只存储列表
                        self.data = content
                        self.profile = {}
            except:
                self.data = []
                self.profile = {}
        else:
            self.data = []
            self.profile = {}

    def save_data(self):
        file_path = os.path.join(os.getcwd(), 'health_backup.json')
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump({'profile': self.profile, 'records': self.data}, f, ensure_ascii=False, indent=2)

    def add_record(self):
        # 获取输入，统一将中文逗号、中文冒号替换为英文符号
        date = self.ids.date_input.text.strip() or datetime.now().strftime('%Y-%m-%d')
        type_ = self.ids.type_spinner.text
        desc = self.ids.desc_input.text.strip().replace('，', ',').replace('：', ':')
        value_text = self.ids.value_input.text.strip().replace('，', ',')

        # ---------- 通用检查：描述或数值缺失时的处理 ----------
        if not desc and type_ not in ['起床时间', '睡眠时间']:
            self.show_info_popup("提示", "请填写描述")
            return

        value = 0.0

        # ---------- 饮食记录（早餐/午餐/晚餐） ----------
        if type_ in ['早餐', '午餐', '晚餐', '零食']:
            foods = [f.strip() for f in desc.split(',') if f.strip()]
            grams_list = [g.strip() for g in value_text.split(',') if g.strip()]

            if not foods:
                self.show_info_popup("提示", "请至少填写一种食物")
                return
            if not value_text or not grams_list:
                self.show_info_popup("提示", "请填写每种食物的克数，用逗号分隔")
                return
            if len(foods) != len(grams_list):
                self.show_info_popup("提示", f"食物数量({len(foods)})与克数数量({len(grams_list)})不一致")
                return

            total_calories = 0.0
            for food, gram_str in zip(foods, grams_list):
                try:
                    grams = float(gram_str)
                except ValueError:
                    self.show_info_popup("提示", f"克数“{gram_str}”不是有效数字")
                    return
                calories_per_100g = self.ai_manager.get_food_calories(food)
                if calories_per_100g is None:
                    self.show_info_popup("提示", f"无法获取“{food}”的热量，请手动输入总热量或稍后再试")
                    return
                total_calories += (calories_per_100g / 100.0) * grams
            value = total_calories

        # ---------- 运动记录 ----------
        elif type_ == '运动':
            exercises = [e.strip() for e in desc.split(',') if e.strip()]
            minutes_list = [m.strip() for m in value_text.split(',') if m.strip()]

            if not exercises:
                self.show_info_popup("提示", "请至少填写一项运动")
                return
            if not value_text or not minutes_list:
                self.show_info_popup("提示", "请填写每项运动的时长，用逗号分隔")
                return
            if len(exercises) != len(minutes_list):
                self.show_info_popup("提示", f"运动数量({len(exercises)})与时长数量({len(minutes_list)})不一致")
                return

            total_consumption = 0.0
            for exercise, minute_str in zip(exercises, minutes_list):
                try:
                    minutes = float(minute_str)
                except ValueError:
                    self.show_info_popup("提示", f"时长“{minute_str}”不是有效数字")
                    return
                kcal_per_30min = self.ai_manager.get_exercise_consumption(exercise)
                if kcal_per_30min is None:
                    self.show_info_popup("提示", f"无法获取“{exercise}”的消耗热量，请手动输入总消耗")
                    return
                total_consumption += (kcal_per_30min / 30.0) * minutes
            value = total_consumption

        # ---------- 起床/睡眠时间 ----------
        elif type_ in ['起床时间', '睡眠时间']:
            if desc:
                import re
                # 支持中文冒号已替换，格式应为 HH:MM
                if not re.match(r'^\d{1,2}:\d{2}$', desc):
                    self.show_info_popup("提示", "时间格式应为 HH:MM，例如 07:30")
                    return
                time_str = desc
            else:
                time_str = datetime.now().strftime('%H:%M')
            desc = time_str  # 描述保存时间字符串
            # value 保持 0

        # ---------- 血压 ----------
        elif type_ == '血压':
            parts = desc.split('/')
            if len(parts) != 3:
                self.show_info_popup("提示", "血压格式应为：收缩压/舒张压/心率，例如 120/80/70")
                return
            try:
                systolic = int(parts[0].strip())
                diastolic = int(parts[1].strip())
                heart_rate = int(parts[2].strip())
            except ValueError:
                self.show_info_popup("提示", "血压和心率必须为数字")
                return

            bp_status = 'normal'
            if systolic > 120 or diastolic > 80:
                bp_status = 'high'
            elif systolic < 90 or diastolic < 60:
                bp_status = 'low'

            hr_status = 'normal'
            if heart_rate > 100:
                hr_status = 'fast'
            elif heart_rate < 60:
                hr_status = 'slow'

            messages = []
            for rule in self.message_rules:
                if rule.get('type') == '血压' and rule.get('condition') == bp_status:
                    messages.append(rule.get('reminder'))
                elif rule.get('type') == '心率' and rule.get('condition') == hr_status:
                    messages.append(rule.get('reminder'))

            if messages:
                self.show_reminder_popup('\n'.join(messages))

            value = 0.0  # 血压不设数值，仅记录描述

        # ---------- 其他类型（手动输入数值） ----------
        else:
            try:
                value = float(value_text) if value_text else 0.0
            except ValueError:
                self.show_info_popup("提示", "数值请输入有效数字")
                return

        # 保存记录
        self.data.append({
            'date': date,
            'type': type_,
            'desc': desc,
            'value': value
        })
        self.save_data()

        # 新增：更新AI状态（健康节律）
        ai_state = AIState()
        ai_state.record_health_activity()
        
        # 清空输入
        self.ids.desc_input.text = ''
        self.ids.value_input.text = ''
        self.ids.date_input.text = datetime.now().strftime('%Y-%m-%d')
        self.refresh_list()

    def delete_record(self, index):
        if 0 <= index < len(self.data):
            del self.data[index]
            self.save_data()
            self.refresh_list()

    def refresh_list(self):
        records_list = self.ids.records_list
        records_list.clear_widgets()

        # 按月份和日期分组
        months = OrderedDict()
        for i, rec in enumerate(self.data):
            date = rec.get('date', '')
            if len(date) >= 7:
                month = date[:7]
            else:
                month = '未知月份'
            if month not in months:
                months[month] = OrderedDict()
            if date not in months[month]:
                months[month][date] = []
            months[month][date].append((i, rec))

        # 按月份倒序排列
        for month in sorted(months.keys(), reverse=True):
            # 月份标题按钮
            month_btn = Button(
                text=month,
                size_hint_y=None,
                height=40,
                background_normal='',
                background_color=(0, 0, 0, 0.5),
                color=(1, 1, 1, 1),
                font_name='Chinese'
            )

            # 月份内容容器
            month_content = GridLayout(
                cols=1,
                size_hint_y=None,
                spacing=0
            )
            month_content.bind(minimum_height=month_content.setter('height'))
            month_content.collapsed = False  # 初始展开

            # 该月份内的日期分组
            for date in sorted(months[month].keys(), reverse=True):
                # 日期标题按钮
                date_btn = Button(
                    text=date,
                    size_hint_y=None,
                    height=30,
                    background_normal='',
                    background_color=(0.2, 0.2, 0.2, 0.5),
                    color=(1, 1, 1, 1),
                    font_name='Chinese'
                )

                # 日期内容容器
                date_content = GridLayout(
                    cols=1,
                    size_hint_y=None,
                    spacing=2
                )
                date_content.bind(minimum_height=date_content.setter('height'))
                date_content.collapsed = False  # 初始展开

                # 添加该日期的所有记录
                for idx, rec in months[month][date]:
                    type_text = rec['type']
                    desc = rec['desc']
                    value = rec['value']
                    if type_text == '运动':
                        text = f"{type_text} | {desc} | {value:.1f}千卡"
                    elif type_text in ['早餐', '午餐', '晚餐', '零食']:
                        text = f"{type_text} | {desc} | {value:.1f}千卡"
                    elif type_text in ['起床时间', '睡眠时间']:
                        text = f"{type_text} | {desc}"
                    elif type_text == '血压':
                        text = f"血压 | {desc}"
                    else:
                        text = f"{type_text} | {desc} | {value}"

                    # 整行按钮，点击打开编辑弹窗
                    record_btn = Button(
                        text=text,
                        size_hint_y=None,
                        height=30,
                        background_normal='',
                        background_color=(0, 0, 0, 0),
                        color=(1, 1, 1, 1),
                        font_name='Chinese',
                        halign='left',
                        text_size=(None, 30),
                        valign='middle'
                    )
                    record_btn.bind(on_release=lambda instance, idx=idx: self.show_edit_popup(idx))
                    date_content.add_widget(record_btn)

                # 日期标题点击折叠/展开
                def toggle_date(instance, content=date_content):
                    if content.collapsed:
                        content.height = content.minimum_height
                        content.opacity = 1
                        content.collapsed = False
                    else:
                        content.height = 0
                        content.opacity = 0
                        content.collapsed = True
                date_btn.bind(on_release=toggle_date)

                # 日期分组容器（标题+内容）
                date_group = GridLayout(
                    cols=1,
                    size_hint_y=None,
                    spacing=0
                )
                date_group.bind(minimum_height=date_group.setter('height'))
                date_group.add_widget(date_btn)
                date_group.add_widget(date_content)
                month_content.add_widget(date_group)

            # 月份标题点击折叠/展开
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

            # 月份总容器（标题+内容）
            month_group = GridLayout(
                cols=1,
                size_hint_y=None,
                spacing=0
            )
            month_group.bind(minimum_height=month_group.setter('height'))
            month_group.add_widget(month_btn)
            month_group.add_widget(month_content)

            records_list.add_widget(month_group)

    def show_edit_popup(self, record_index):
        """显示编辑记录弹窗，包含修改和删除功能（布局优化）"""
        if record_index < 0 or record_index >= len(self.data):
            return

        rec = self.data[record_index]
        date_orig = rec.get('date', '')
        type_orig = rec.get('type', '')
        desc_orig = rec.get('desc', '')
        value_orig = rec.get('value', 0.0)

        # 根布局：垂直排列，顶部为滚动区域，底部为按钮栏
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)

        # 滚动区域
        scroll = ScrollView(
            size_hint=(1, 1),
            bar_width=10,
            scroll_type=['bars', 'content']
        )

        # 表单网格，设置高度自适应
        grid = GridLayout(
            cols=2,
            spacing=10,
            size_hint_y=None,
            padding=10
        )
        grid.bind(minimum_height=grid.setter('height'))

        # 日期
        grid.add_widget(Label(text="日期:", font_name='Chinese', color=(0,0,0,1), size_hint_y=None, height=40))
        date_input = TextInput(text=date_orig, multiline=False, font_name='Chinese', size_hint_y=None, height=40)
        grid.add_widget(date_input)

        # 类型
        grid.add_widget(Label(text="类型:", font_name='Chinese', color=(0,0,0,1), size_hint_y=None, height=40))
        type_spinner = Spinner(
            text=type_orig,
            values=["早餐", "午餐", "晚餐", "零食", "运动", "起床时间", "睡眠时间", "血压"],
            font_name='Chinese',
            size_hint_y=None,
            height=40
        )
        grid.add_widget(type_spinner)

        # 描述
        grid.add_widget(Label(text="描述:", font_name='Chinese', color=(0,0,0,1), size_hint_y=None, height=40))
        desc_input = TextInput(text=desc_orig, multiline=False, font_name='Chinese', size_hint_y=None, height=40)
        grid.add_widget(desc_input)

        # 数值
        grid.add_widget(Label(text="数值:", font_name='Chinese', color=(0,0,0,1), size_hint_y=None, height=40))
        value_input = TextInput(text=str(value_orig), multiline=False, font_name='Chinese', size_hint_y=None, height=40)
        grid.add_widget(value_input)

        scroll.add_widget(grid)
        content.add_widget(scroll)

        # 按钮栏（固定高度）
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
            title='编辑健康记录',
            content=content,
            size_hint=(0.9, 0.85)  # 增加高度，保证滚动区域充足
        )

        def save_changes(instance):
            new_date = date_input.text.strip()
            new_type = type_spinner.text
            new_desc = desc_input.text.strip()
            new_value_text = value_input.text.strip()

            if not new_date:
                new_date = datetime.now().strftime('%Y-%m-%d')
            if not new_desc and new_type not in ['起床时间', '睡眠时间']:
                self.show_info_popup("提示", "描述不能为空")
                return

            try:
                new_value = float(new_value_text) if new_value_text else 0.0
            except ValueError:
                self.show_info_popup("提示", "数值必须为数字")
                return

            self.data[record_index] = {
                'date': new_date,
                'type': new_type,
                'desc': new_desc,
                'value': new_value
            }
            self.save_data()
            self.refresh_list()
            popup.dismiss()

        def delete_and_close(instance):
            self.delete_record(record_index)
            popup.dismiss()

        save_btn.bind(on_release=save_changes)
        delete_btn.bind(on_release=delete_and_close)

        popup.open()

    def show_profile_popup(self):
        """显示基本信息录入弹窗（修复布局堆叠）"""
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)

        # 固定高度滚动区域，参考记账模块 edit_popup
        scroll = ScrollView(size_hint=(1, None), size=(Window.width, Window.height * 0.6))
        form = GridLayout(cols=2, spacing=5, size_hint_y=None)
        form.bind(minimum_height=form.setter('height'))

        # 身高
        form.add_widget(Label(text="身高(cm):", font_name='Chinese', color=(0,0,0,1), size_hint_y=None, height=40))
        height_input = TextInput(text=str(self.profile.get('height', '')), multiline=False, font_name='Chinese', size_hint_y=None, height=40)
        form.add_widget(height_input)

        # 体重
        form.add_widget(Label(text="体重(kg):", font_name='Chinese', color=(0,0,0,1), size_hint_y=None, height=40))
        weight_input = TextInput(text=str(self.profile.get('weight', '')), multiline=False, font_name='Chinese', size_hint_y=None, height=40)
        form.add_widget(weight_input)

        # 年龄
        form.add_widget(Label(text="年龄:", font_name='Chinese', color=(0,0,0,1), size_hint_y=None, height=40))
        age_input = TextInput(text=str(self.profile.get('age', '')), multiline=False, font_name='Chinese', size_hint_y=None, height=40)
        form.add_widget(age_input)

        # 性别
        form.add_widget(Label(text="性别:", font_name='Chinese', color=(0,0,0,1), size_hint_y=None, height=40))
        gender_spinner = Spinner(
            text=self.profile.get('gender', '男'),
            values=['男', '女'],
            font_name='Chinese',
            size_hint_y=None,
            height=40
        )
        form.add_widget(gender_spinner)

        scroll.add_widget(form)
        content.add_widget(scroll)

        # 按钮行
        btn_box = BoxLayout(size_hint_y=None, height=50, spacing=10)
        save_btn = Button(
            text='保存',
            background_normal='',
            background_color=(0.2, 0.6, 0.2, 0.8),
            color=(1, 1, 1, 1),
            font_name='Chinese'
        )
        cancel_btn = Button(
            text='取消',
            background_normal='',
            background_color=(0.6, 0.6, 0.6, 0.8),
            color=(1, 1, 1, 1),
            font_name='Chinese'
        )
        btn_box.add_widget(save_btn)
        btn_box.add_widget(cancel_btn)
        content.add_widget(btn_box)

        popup = Popup(title='基本信息', content=content, size_hint=(0.9, 0.8))

        def save(instance):
            try:
                height = float(height_input.text.strip()) if height_input.text.strip() else 0.0
                weight = float(weight_input.text.strip()) if weight_input.text.strip() else 0.0
                age = int(age_input.text.strip()) if age_input.text.strip() else 0
            except ValueError:
                self.show_info_popup("提示", "请输入有效的数字")
                return
            self.profile = {
                'height': height,
                'weight': weight,
                'age': age,
                'gender': gender_spinner.text
            }
            self.save_data()
            popup.dismiss()

        cancel_btn.bind(on_release=popup.dismiss)
        save_btn.bind(on_release=save)
        popup.open()

    def ai_health_assessment(self):
        """调用 AI 评估当日和昨日的饮食运动健康情况"""
        # 获取最近两天的日期
        today = datetime.now()
        yesterday = today - timedelta(days=1)
        dates = [today.strftime('%Y-%m-%d'), yesterday.strftime('%Y-%m-%d')]

        # 筛选相关记录
        relevant_records = [rec for rec in self.data if rec.get('date') in dates]
        if not relevant_records:
            self.show_info_popup("提示", "最近两天暂无健康记录，无法评估")
            return

        # 构造记录摘要
        lines = []
        for rec in relevant_records:
            type_ = rec.get('type', '')
            desc = rec.get('desc', '')
            value = rec.get('value', 0)
            if type_ in ['早餐', '午餐', '晚餐']:
                lines.append(f"{rec['date']} {type_}：{desc}，热量{value:.1f}千卡")
            elif type_ == '运动':
                lines.append(f"{rec['date']} 运动：{desc}，消耗{value:.1f}千卡")
            elif type_ in ['起床时间', '睡眠时间']:
                lines.append(f"{rec['date']} {type_}：{desc}")
            elif type_ == '血压':
                lines.append(f"{rec['date']} 血压：{desc}")
            else:
                lines.append(f"{rec['date']} {type_}：{desc}，数值{value}")
        records_text = "\n".join(lines)

        # 加入基本信息
        profile_text = ""
        if self.profile:
            profile_text = f"用户基本信息：身高{self.profile.get('height', '未知')}cm，体重{self.profile.get('weight', '未知')}kg，年龄{self.profile.get('age', '未知')}，性别{self.profile.get('gender', '未知')}\n"

        # 口吻配置
        tone = self.ai_manager.config.get('tone', '专业、友善')

        prompt = (f"请根据以下信息评估用户最近两天的健康状况，并提出简要建议。\n{profile_text}\n健康记录：\n{records_text}\n\n请以{tone}的口吻回答，不超过300字。"
                   "请不要用表格等进行回复，直接以文字条目回复即可")
        
        result = self.ai_manager.query_deepseek(prompt)
        if result:
            self.show_text_popup("AI健康评估", result)
        else:
            self.show_info_popup("提示", "AI调用失败，请检查API配置")

    def ai_exercise_plan(self):
        """调用 AI 制定锻炼计划"""
        profile_text = ""
        if self.profile:
            profile_text = f"用户基本信息：身高{self.profile.get('height', '未知')}cm，体重{self.profile.get('weight', '未知')}kg，年龄{self.profile.get('age', '未知')}，性别{self.profile.get('gender', '未知')}\n"

        # 获取最近的运动记录
        recent_exercise = [rec for rec in self.data if rec.get('type') == '运动' and rec.get('date') >= (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')]
        exercise_text = ""
        if recent_exercise:
            for rec in recent_exercise:
                exercise_text += f"{rec['date']} 运动：{rec['desc']}，时长/消耗{rec['value']}千卡\n"
        else:
            exercise_text = "最近一周无运动记录。\n"

        tone = self.ai_manager.config.get('tone', '专业、友善')

        prompt = (f"请根据以下用户信息制定一个适合的每周锻炼计划。\n{profile_text}\n最近运动情况：\n{exercise_text}\n请以{tone}的口吻回答，计划应具体可行。"
                  "请不要用表格等进行回复，直接以文字条目回复即可")

        result = self.ai_manager.query_deepseek(prompt)
        if result:
            self.show_text_popup("AI锻炼计划", result)
        else:
            self.show_info_popup("提示", "AI调用失败，请检查API配置")

    def show_text_popup(self, title, text):
        """显示长文本弹窗，支持滚动，并增加保存为 txt 按钮"""
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)

        scroll = ScrollView(size_hint=(1, None), size=(Window.width * 0.9, Window.height * 0.6))
        label = Label(
            text=text,
            size_hint_y=None,
            halign='left',
            valign='top',
            font_name='Chinese',
            text_size=(None, None)
        )

        def update_text_size(instance, value):
            instance.text_size = (instance.width, None)
        label.bind(width=update_text_size)
        label.bind(texture_size=label.setter('size'))
        scroll.add_widget(label)
        content.add_widget(scroll)

        # 按钮行：保存、关闭
        btn_box = BoxLayout(size_hint_y=None, height=50, spacing=10)

        save_btn = Button(
            text='保存为txt',
            background_normal='',
            background_color=(0.2, 0.6, 0.2, 0.8),
            color=(1, 1, 1, 1),
            font_name='Chinese',
            on_release=lambda *a: self.save_text_to_file(title, text)
        )
        close_btn = Button(
            text='关闭',
            background_normal='',
            background_color=(0.2, 0.2, 0.8, 0.8),
            color=(1, 1, 1, 1),
            font_name='Chinese',
            on_release=lambda *a: popup.dismiss()
        )
        btn_box.add_widget(save_btn)
        btn_box.add_widget(close_btn)
        content.add_widget(btn_box)

        popup = Popup(title=title, content=content, size_hint=(0.9, 0.8))
        popup.open()

    def save_text_to_file(self, title, text):
        """将文本保存为 txt 文件，文件名包含标题和时间戳"""
        try:
            # 生成文件名（去除标题中的空格和特殊字符）
            safe_title = "".join(c for c in title if c.isalnum() or c in ('_', '-'))
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{safe_title}_{timestamp}.txt"
            file_path = os.path.join(os.getcwd(), filename)

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(text)

            self.show_info_popup("保存成功", f"文件已保存至：\n{file_path}")
        except Exception as e:
            self.show_info_popup("保存失败", f"保存文件时出错：{e}")

    def go_to_main(self):
        app = App.get_running_app()
        if app and app.sm:
            app.sm.current = 'main'

    def load_message_rules(self):
        """
        从外置 health_messages.json 文件加载提醒规则。
        返回规则列表，每个规则为字典，包含 type 和 reminder 字段。
        """
        rules = []
        file_path = os.path.join(os.getcwd(), 'health_messages.json')
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    rules = data.get('rules', [])
            except Exception as e:
                print(f"加载健康提醒规则失败：{e}")
        return rules

    def check_reminders(self):
        if not self.message_rules:
            return
        today = datetime.now().strftime('%Y-%m-%d')
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

        today_recs = [r for r in self.data if r.get('date') == today]
        yest_recs = [r for r in self.data if r.get('date') == yesterday]

        # 1. 起床时间
        today_wake = [r for r in today_recs if r.get('type') == '起床时间']
        if not today_wake:
            self.popup_single_reminder('未记录起床时间')
            return

        # 2. 昨日睡眠时间
        yest_sleep = [r for r in yest_recs if r.get('type') == '睡眠时间']
        if not yest_sleep:
            self.popup_single_reminder('未记录睡眠时间')
            return

        # 3. 睡眠时长检查
        wake_str = today_wake[-1].get('desc', '')
        sleep_str = yest_sleep[-1].get('desc', '')
        wake_min = self.time_to_minutes(wake_str)
        sleep_min = self.time_to_minutes(sleep_str)
        if wake_min is None or sleep_min is None:
            self.popup_single_reminder('未记录起床时间')  # 格式错误，按未记录处理
            return

        diff_min = wake_min - sleep_min
        if diff_min < 0:
            diff_min += 24 * 60
        hours = diff_min / 60.0
        if hours < 6:
            self.popup_single_reminder('睡眠不足')
            return
        elif hours > 9:
            self.popup_single_reminder('睡眠过量')
            return
        # 睡眠正常，继续

        # 4. 晚餐缺失检查（当前时间晚于19点）
        now = datetime.now()
        if now.hour >= 19:
            meal_types = ['早餐', '午餐', '晚餐']
            missing_meals = [mt for mt in meal_types if not any(r.get('type') == mt for r in today_recs)]
            if missing_meals:
                self.popup_single_reminder('早/中/晚餐未记录')
                return

        # 5. 饮食热量与运动消耗
        diet_cal = sum(r.get('value', 0) for r in today_recs if r.get('type') in ['早餐', '午餐', '晚餐'])
        exercise_cal = sum(r.get('value', 0) for r in today_recs if r.get('type') == '运动')
        net_cal = diet_cal - exercise_cal
        if net_cal < 1200:
            self.popup_single_reminder('饮食热量过低')
            return
        elif net_cal > 2500:
            self.popup_single_reminder('饮食热量过高')
            return
        # 热量适当，继续检查血压

        # 6. 血压检查
        bp_recs = [r for r in today_recs if r.get('type') == '血压']
        if not bp_recs:
            self.popup_single_reminder('未记录血压')
            return

        latest_bp = bp_recs[-1]
        bp_desc = latest_bp.get('desc', '')
        try:
            parts = bp_desc.split('/')
            systolic = int(parts[0].strip())
            diastolic = int(parts[1].strip())
            heart_rate = int(parts[2].strip())
        except:
            self.popup_single_reminder('未记录血压')  # 格式错误
            return

        # 血压状态
        if systolic > 120 or diastolic > 80:
            bp_status = '过高'
        elif systolic < 90 or diastolic < 60:
            bp_status = '过低'
        else:
            bp_status = '正常'

        # 心率状态
        if heart_rate > 100:
            hr_status = '过速'
        elif heart_rate < 60:
            hr_status = '过缓'
        else:
            hr_status = '正常'

        # 构建类型字符串
        type_str = f'血压{bp_status}心率{hr_status}'
        self.popup_single_reminder(type_str)

    def popup_single_reminder(self, type_str):
        """根据类型弹出单条提醒，从 health_messages.json 中查找对应文本"""
        reminder = None
        for rule in self.message_rules:
            if rule.get('type') == type_str:
                reminder = rule.get('reminder')
                break
        if reminder is None:
            reminder = type_str  # 未配置时直接显示类型名
        self.show_reminder_popup(reminder)

    def time_to_minutes(self, time_str):
        """将 HH:MM 格式转换为分钟数，无效返回 None"""
        import re
        if not re.match(r'^\d{1,2}:\d{2}$', time_str):
            return None
        try:
            h, m = time_str.split(':')
            return int(h) * 60 + int(m)
        except:
            return None
    
    def show_reminder_popup(self, message):
        """弹出健康记录提醒窗口"""
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
            text='知道了',
            size_hint_y=None,
            height=40,
            background_normal='',
            background_color=(0.2, 0.6, 0.2, 0.8),
            color=(1, 1, 1, 1),
            font_name='Chinese'
        )
        content.add_widget(close_btn)

        popup = Popup(
            title='健康提醒',
            content=content,
            size_hint=(0.8, 0.5)
        )
        close_btn.bind(on_release=popup.dismiss)
        popup.open()

    def show_info_popup(self, title, message):
        """通用信息弹窗，用于显示提示"""
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
            background_color=(0.2, 0.6, 0.2, 0.8),
            color=(1, 1, 1, 1),
            font_name='Chinese'
        )
        content.add_widget(close_btn)

        popup = Popup(
            title=title,
            content=content,
            size_hint=(0.8, 0.5)
        )
        close_btn.bind(on_release=popup.dismiss)
        popup.open()

class HealthScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.health_root = HealthRoot()           # 保存引用
        self.add_widget(self.health_root)

    def on_enter(self):
        self.health_root.check_reminders()