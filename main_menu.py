from kivy.config import Config
Config.set('graphics', 'width', '400')
Config.set('graphics', 'height', '712')
Config.set('graphics', 'resizable', False)
import os
os.environ['SDL_IME_SHOW_UI'] = '1'   # 强制 SDL 显示输入法 UI

from kivy.config import Config
#Config.set('kivy', 'keyboard_mode', 'systemandmulti')  # 启用系统键盘和多点触控键盘
Config.set('kivy', 'keyboard_layout', 'zh_CN')         # 布局设为中文（视系统而定）

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout   # 新增
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.video import Video               # 新增
from kivy.uix.popup import Popup
from kivy.core.text import LabelBase
from ai_manager import AIManager
import json
import os

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

class MainMenuScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = FloatLayout()   # 根布局改为 FloatLayout

        # 背景视频
        video = Video(
            source='main_menu.mp4',
            state='play',
            options={'eos': 'loop'},
            allow_stretch=True,
            keep_ratio=False,
            volume=0,
            size_hint=(1, 1),
            pos_hint={'x': 0, 'y': 0}
        )
        root.add_widget(video)

        # 内容层（透明背景）
        content = BoxLayout(
            orientation='vertical',
            padding=50,
            spacing=20,
            size_hint=(1, 1),
            pos_hint={'x': 0, 'y': 0}
        )
        content.add_widget(Label(
            text='智能助理',
            font_name='Chinese',
            font_size=32,
            size_hint_y=None,
            height=80,
            color=(1, 1, 1, 1)        # 白色文字
        ))
        content.add_widget(Label(
            text='欢迎使用个人生活助手',
            font_name='Chinese',
            font_size=18,
            size_hint_y=None,
            height=40,
            color=(1, 1, 1, 1)
        ))
        # 按钮透明化
        btn_params = dict(
            font_name='Chinese',
            font_size=22,
            size_hint_y=None,
            height=60,
            background_normal='',
            background_down='',
            background_color=(1, 1, 1, 0.2),   # 半透明白
            color=(1, 1, 1, 1)
        )
        btn_account = Button(text='记账管理', **btn_params)
        btn_account.bind(on_release=lambda *a: self.go_to('accounting'))
        content.add_widget(btn_account)

        btn_health = Button(text='健康管理', **btn_params)
        btn_health.bind(on_release=lambda *a: self.go_to('health'))
        content.add_widget(btn_health)

        btn_ai = Button(text='AI助手', **btn_params)
        btn_ai.bind(on_release=lambda *a: self.go_to('ai_chat'))
        content.add_widget(btn_ai)

        btn_refresh = Button(
            text='刷新文本',
            font_name='Chinese',
            font_size=22,
            size_hint_y=None,
            height=60,
            background_normal='',
            background_down='',
            background_color=(1, 1, 1, 0.2),
            color=(1, 1, 1, 1),
            on_release=lambda *a: self.refresh_texts()
        )
        content.add_widget(btn_refresh)

        btn_exit = Button(text='退出程序', **btn_params)
        btn_exit.bind(on_release=lambda *a: self.exit_app())
        content.add_widget(btn_exit)

        root.add_widget(content)
        self.add_widget(root)

    def go_to(self, screen_name):
        app = App.get_running_app()
        if app and app.sm:
            app.sm.current = screen_name

    def exit_app(self):
        app = App.get_running_app()
        if app:
            app.stop()

    def refresh_texts(self):
        """调用 AI 更新 health_messages.json 和 messages.json，并应用 tone 口吻"""
        ai = AIManager()
        tone = ai.config.get('tone', '专业、友善')  # 读取配置的口吻

        prompt = (
            f"请以{tone}的口吻生成两个 JSON 对象，分别用于健康提醒和记账提示。"
            "第一个 JSON 对象对应文件 health_messages.json，格式为：{\"rules\": [{\"type\": \"起床时间\", \"reminder\": \"...\"}, ...]}，"
            "其中 type 可以是 '起床时间'、'睡眠时间'、'血压'、'心率' 等；对于血压和心率，还需要 condition 字段（normal/high/low 或 normal/fast/slow）和对应的提醒文本。"
            "第二个 JSON 对象对应文件 messages.json，格式为：{\"rules\": [{\"type\": \"收入/支出\", \"category\": \"餐饮/交通/...\", \"min_amount\": 0, \"max_amount\": null, \"message\": \"...\"}, ...]}，"
            "其中 type 为 '收入' 或 '支出'，category 为记账分类，金额区间用于匹配。"
            "请只返回一个包含两个键的 JSON 对象，键名分别为 'health' 和 'account'，值分别为上述两个规则的 JSON 对象。"
            "不要包含任何额外解释。"
        )
        result = ai.query_deepseek(prompt)
        if not result:
            self.show_info_popup("刷新失败", "AI 调用失败，请检查 API 配置")
            return

        try:
            data = json.loads(result)
            health_data = data.get('health', {})
            account_data = data.get('account', {})

            # 写入 health_messages.json
            health_path = os.path.join(os.getcwd(), 'health_messages.json')
            with open(health_path, 'w', encoding='utf-8') as f:
                json.dump(health_data, f, ensure_ascii=False, indent=2)

            # 写入 messages.json
            account_path = os.path.join(os.getcwd(), 'messages.json')
            with open(account_path, 'w', encoding='utf-8') as f:
                json.dump(account_data, f, ensure_ascii=False, indent=2)

            self.show_info_popup("刷新成功", "两个文本库已更新")
        except Exception as e:
            self.show_info_popup("刷新失败", f"解析或写入出错：{e}")

    def show_info_popup(self, title, message):
        """通用信息弹窗"""
        content = BoxLayout(orientation='vertical', padding=20, spacing=10)
        label = Label(text=message, font_name='Chinese', halign='center')
        content.add_widget(label)
        close_btn = Button(
            text='确定',
            size_hint_y=None,
            height=40,
            background_normal='',
            background_color=(0.2, 0.2, 0.8, 0.8),
            color=(1,1,1,1),
            font_name='Chinese'
        )
        content.add_widget(close_btn)
        popup = Popup(title=title, content=content, size_hint=(0.8, 0.4))
        close_btn.bind(on_release=popup.dismiss)
        popup.open()

class AssistantApp(App):
    def build(self):
        self.sm = ScreenManager()
        from account import AccountingScreen
        from health import HealthScreen
        from ai_chat import AIChatScreen

        self.sm.add_widget(MainMenuScreen(name='main'))
        self.sm.add_widget(AccountingScreen(name='accounting'))
        self.sm.add_widget(HealthScreen(name='health'))

        self.ai_chat_screen = AIChatScreen(name='ai_chat')  # 仅创建一次
        self.sm.add_widget(self.ai_chat_screen)

        return self.sm

    def on_stop(self):
        # 立即导出备份
        #self.export_data(silent=True)
        # 更新长期记忆池
        if hasattr(self, 'ai_chat_screen'):
            conversation_history = self.ai_chat_screen.conversation_history
            ai_state = self.ai_chat_screen.ai_state
            ai_state.update_memory_pool(conversation_history)
        """应用关闭时自动导出各模块数据"""
        if hasattr(self, 'accounting_root'):
            self.accounting_root.export_data(silent=True)
        if hasattr(self, 'health_root'):
            self.health_root.save_data()

if __name__ == '__main__':
    AssistantApp().run()