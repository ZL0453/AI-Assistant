# ai_chat.py
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.spinner import Spinner
from kivy.uix.switch import Switch
from kivy.uix.popup import Popup
from kivy.core.text import LabelBase
from kivy.app import App
from kivy.core.window import Window
from kivy.uix.video import Video
from kivy.uix.floatlayout import FloatLayout
from datetime import datetime
import json
import os
import requests
import threading
from ai_state import AIState

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

class AIChatScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.load_config()
        self.ai_state = AIState()  # 已有
        # 设置默认值（与设置弹窗中的控件状态对应）
        self.memory_on = True
        self.deep_think = False
        self.web_search = False
        self.selected_model = 'deepseek-chat'
        self.build_ui()
        self.conversation_history = []
        self.pending_files = []
        self.update_background()

    def is_daytime(self):
        """判断当前是否为白天（6:00-18:00）"""
        hour = datetime.now().hour
        return 6 <= hour < 18

    def update_background(self):
        """根据当前时间切换 AI 助手背景视频"""
        video_file = 'ai_chat_day.mp4' if self.is_daytime() else 'ai_chat_night.mp4'
        video_path = os.path.join(os.getcwd(), video_file)
        if os.path.exists(video_path):
            self.bg_video.source = video_path
            self.bg_video.state = 'play'
            self.bg_video.volume = 0   # 静音
            print(f"切换AI助手背景视频：{video_file}")
        else:
            print(f"警告：视频文件不存在 {video_path}，背景将保持纯色。")
            self.bg_video.source = ''

    def load_config(self):
        config_path = os.path.join(os.getcwd(), 'ai_config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        else:
            self.config = {"api_key": "", "base_url": "https://api.deepseek.com/v1", "tone": "专业、友善", "name": "AI"}
        # 确保 name 字段存在
        if 'name' not in self.config:
            self.config['name'] = 'AI'

    def build_ui(self):
        # 根布局改为 FloatLayout，用于叠加背景视频和内容
        root = FloatLayout()

        # 背景视频（底层）
        self.bg_video = Video(
            source='',                  # 初始为空，稍后设置
            state='play',
            options={'eos': 'loop'},
            allow_stretch=True,
            keep_ratio=False,
            volume=0,                     # 静音
            size_hint=(1, 1),
            pos_hint={'x': 0, 'y': 0}
        )
        root.add_widget(self.bg_video)

        # 内容层（BoxLayout，透明背景）
        content = BoxLayout(orientation='vertical', padding=10, spacing=5, size_hint=(1, 1), pos_hint={'x': 0, 'y': 0})

        # 顶部标题
        title = Label(
            text='AI 智能助手',
            font_name='Chinese',
            font_size=24,
            size_hint_y=None,
            height=50,
            color=(1, 1, 1, 1)      # 白色文字，透明背景
        )
        content.add_widget(title)

        # 聊天记录显示区域
        self.chat_scroll = ScrollView(size_hint=(1, 1))
        self.chat_box = GridLayout(cols=1, spacing=5, size_hint_y=None)
        self.chat_box.bind(minimum_height=self.chat_box.setter('height'))
        self.chat_scroll.add_widget(self.chat_box)
        content.add_widget(self.chat_scroll)

        # 底部输入区域 + 按钮
        input_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=50, spacing=5)
        self.input_field = TextInput(
            hint_text='请输入消息或拖入文件...',
            font_name='Chinese',
            multiline=False,
            size_hint_x=0.7,
            background_normal='',
            background_color=(0,0,0,0.3),
            foreground_color=(1,1,1,1)
        )
        send_btn = Button(
            text='发送',
            font_name='Chinese',
            size_hint_x=0.15,
            background_normal='',
            background_color=(0.2,0.6,0.2,0.8),
            color=(1,1,1,1),
            on_release=lambda *a: self.send_message()
        )
        settings_btn = Button(
            text='设置',
            font_name='Chinese',
            size_hint_x=0.15,
            background_normal='',
            background_color=(0.2,0.2,0.8,0.8),
            color=(1,1,1,1),
            on_release=lambda *a: self.open_settings()
        )
        input_box.add_widget(self.input_field)
        input_box.add_widget(send_btn)
        input_box.add_widget(settings_btn)
        content.add_widget(input_box)

        root.add_widget(content)
        self.add_widget(root)

        # 绑定拖拽事件
        Window.bind(on_dropfile=self.on_drop_file)

    def go_to_main(self):
        app = App.get_running_app()
        if app and app.sm:
            app.sm.current = 'main'

    def add_message(self, text, is_user=False):
        """在聊天区域添加一条消息"""
        prefix = "我: " if is_user else f"{self.config.get('name', 'AI')}: "
        label = Label(
            text=prefix + text,
            font_name='Chinese',
            size_hint_y=None,
            halign='left' if is_user else 'right',
            valign='top',
            text_size=(self.chat_scroll.width - 20, None),
            color=(1,1,1,1) if is_user else (0.8,0.9,1,1)
        )
        label.bind(texture_size=label.setter('size'))
        self.chat_box.add_widget(label)
        self.chat_scroll.scroll_y = 0

    def on_drop_file(self, window, file_path, *args):
        """处理文件拖入事件"""
        if isinstance(file_path, bytes):
            file_path = file_path.decode('utf-8')
        self.pending_files.append(file_path)
        self.add_message(f"已拖入文件: {file_path}", is_user=False)

    def send_message(self):
        user_text = self.input_field.text.strip()
        # 如果有拖入的文件，将其路径附加到消息中
        if self.pending_files:
            file_info = "\n".join([f"[文件] {f}" for f in self.pending_files])
            if user_text:
                user_text = f"{user_text}\n{file_info}"
            else:
                user_text = file_info
            self.pending_files.clear()

        if not user_text:
            return
        self.add_message(f"{user_text}", is_user=True)
        self.input_field.text = ''

        # 调用 API（后台线程，避免阻塞 UI）
        threading.Thread(target=self.call_api, args=(user_text,), daemon=True).start()

    def call_api(self, user_text):
        api_key = self.config.get('api_key', '')
        base_url = self.config.get('base_url', 'https://api.deepseek.com/v1')

        if not api_key:
            self.add_message(f"{self.config.get('name', 'AI')}: 未配置 API 密钥，请检查 ai_config.json", is_user=False)
            return

        system_msg = self.ai_state.get_system_prompt()
        messages = [{"role": "system", "content": system_msg}]
        if self.memory_on:   # 使用属性，而非控件
            messages.extend(self.conversation_history)
        messages.append({"role": "user", "content": user_text})

        # 选择模型
        if self.deep_think:
            model = "deepseek-reasoner"
        else:
            model = self.selected_model

        if self.web_search:
            messages.insert(1, {"role": "system", "content": "请模拟联网搜索的结果回答问题。"})

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "stream": False
        }

        try:
            resp = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            result = resp.json()
            reply = result['choices'][0]['message']['content']
        except Exception as e:
            reply = f"调用失败：{e}"

        if self.memory_on:
            self.conversation_history.append({"role": "user", "content": user_text})
            self.conversation_history.append({"role": "assistant", "content": reply})

        self.ai_state.update_after_chat(user_text, reply)

        from kivy.clock import Clock
        Clock.schedule_once(lambda dt: self.add_message(reply, is_user=False), 0)
        
    def open_settings(self):
        """打开设置弹窗，包含模型、记忆、深度思考、联网搜索和返回主菜单"""
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)

        # 使用 ScrollView 避免堆叠
        scroll = ScrollView(size_hint=(1, None), size=(Window.width * 0.9, Window.height * 0.6))
        form = GridLayout(cols=2, spacing=5, size_hint_y=None)
        form.bind(minimum_height=form.setter('height'))

        # 模型选择
        form.add_widget(Label(text="模型:", font_name='Chinese', color=(0,0,0,1), size_hint_y=None, height=40))
        self.model_spinner = Spinner(
            text=getattr(self, 'selected_model', 'deepseek-chat'),
            values=['deepseek-chat', 'deepseek-reasoner'],
            font_name='Chinese',
            size_hint_y=None,
            height=40
        )
        form.add_widget(self.model_spinner)
        self.deep_switch = Switch(active=self.deep_think)
        self.memory_switch = Switch(active=self.memory_on)
        self.web_switch = Switch(active=self.web_search)

        # 深度思考开关
        form.add_widget(Label(text="深度思考:", font_name='Chinese', color=(0,0,0,1), size_hint_y=None, height=40))
        self.deep_switch = Switch(active=getattr(self, 'deep_think', False))
        form.add_widget(self.deep_switch)

        # 记忆开关
        form.add_widget(Label(text="记忆:", font_name='Chinese', color=(0,0,0,1), size_hint_y=None, height=40))
        self.memory_switch = Switch(active=getattr(self, 'memory_on', True))
        form.add_widget(self.memory_switch)

        # 联网搜索开关
        form.add_widget(Label(text="联网搜索:", font_name='Chinese', color=(0,0,0,1), size_hint_y=None, height=40))
        self.web_switch = Switch(active=getattr(self, 'web_search', False))
        form.add_widget(self.web_switch)

        # 上传文件提示
        form.add_widget(Label(text="文件上传:", font_name='Chinese', color=(0,0,0,1), size_hint_y=None, height=40))
        upload_info = Label(
            text="拖拽文件到界面即可",
            font_name='Chinese',
            color=(0.3,0.3,0.3,1),
            size_hint_y=None,
            height=40
        )
        form.add_widget(upload_info)

        scroll.add_widget(form)
        content.add_widget(scroll)

        # 按钮行
        btn_box = BoxLayout(size_hint_y=None, height=50, spacing=10)
        save_btn = Button(
            text='保存设置',
            background_normal='',
            background_color=(0.2, 0.6, 0.2, 0.8),
            color=(1,1,1,1),
            font_name='Chinese',
            on_release=lambda *a: self.save_settings()
        )
        back_btn = Button(
            text='返回主菜单',
            background_normal='',
            background_color=(0.6,0.2,0.2,0.8),
            color=(1,1,1,1),
            font_name='Chinese'
        )
        back_btn.bind(on_release=self.back_to_main)
        clear_btn = Button(
            text='清空记录',
            background_normal='',
            background_color=(0.8, 0.4, 0.0, 0.8),
            color=(1,1,1,1),
            font_name='Chinese',
            on_release=lambda *a: self.confirm_clear_records()
        )
        btn_box.add_widget(save_btn)
        btn_box.add_widget(back_btn)
        btn_box.add_widget(clear_btn)
        content.add_widget(btn_box)

        self.settings_popup = Popup(
            title='AI 设置',
            content=content,
            size_hint=(0.9, 0.8)
        )
        self.settings_popup.open()

    def save_settings(self):
        self.selected_model = self.model_spinner.text
        self.deep_think = self.deep_switch.active
        self.memory_on = self.memory_switch.active
        self.web_search = self.web_switch.active
        # 关闭弹窗
        if self.settings_popup is not None:
            self.settings_popup.dismiss()
            self.settings_popup = None
        self.add_message("设置已更新", is_user=False)

    def back_to_main(self, *args):
        """返回主菜单并关闭设置弹窗（如果存在）"""
        if self.settings_popup is not None:
            self.settings_popup.dismiss()
            self.settings_popup = None
        self.go_to_main()

    def confirm_clear_records(self):
        """弹出确认对话框，确认后清空聊天记录"""
        content = BoxLayout(orientation='vertical', padding=20, spacing=10)
        label = Label(
            text="确定要清空所有聊天记录吗？",
            font_name='Chinese',
            halign='center'
        )
        content.add_widget(label)

        btn_box = BoxLayout(size_hint_y=None, height=50, spacing=10)
        confirm_btn = Button(
            text='确认清空',
            background_normal='',
            background_color=(0.8, 0.2, 0.2, 0.8),
            color=(1,1,1,1),
            font_name='Chinese'
        )
        cancel_btn = Button(
            text='取消',
            background_normal='',
            background_color=(0.6, 0.6, 0.6, 0.8),
            color=(1,1,1,1),
            font_name='Chinese'
        )
        btn_box.add_widget(confirm_btn)
        btn_box.add_widget(cancel_btn)
        content.add_widget(btn_box)

        popup = Popup(title='清空记录', content=content, size_hint=(0.8, 0.4))

        def do_clear(instance):
            self.clear_records()
            popup.dismiss()
            if self.settings_popup is not None:
                self.settings_popup.dismiss()
                self.settings_popup = None
            self.add_message("记录已清空", is_user=False)

        confirm_btn.bind(on_release=do_clear)
        cancel_btn.bind(on_release=popup.dismiss)
        popup.open()

    def clear_records(self):
        """清空会话历史和聊天显示"""
        self.conversation_history.clear()
        self.chat_box.clear_widgets()
        self.input_field.text = ''


