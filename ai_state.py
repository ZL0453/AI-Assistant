# ai_state.py
import json
import os
from datetime import datetime, timedelta

class AIState:
    def __init__(self, config_file='ai_config.json'):
        self.config_file = config_file
        self.load()

    def load(self):
        path = os.path.join(os.getcwd(), self.config_file)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
        else:
            self.data = {}
        # 初始化默认值
        self.data.setdefault('emotions', {'mood': 50, 'energy': 70, 'tension': 30})
        self.data.setdefault('relationships', {'familiarity': 20, 'trust': 30})
        self.data.setdefault('rhythms', {})
        self.data.setdefault('memory', [])
        self.data.setdefault('persona', '你是一个贴心的生活助手。')

    def save(self):
        path = os.path.join(os.getcwd(), self.config_file)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def get_system_prompt(self):
        """构造包含当前情绪、关系、记忆的系统提示"""
        emotions = self.data['emotions']
        relationships = self.data['relationships']
        memory = self.data['memory']
        persona = self.data['persona']

        prompt = f"{persona}\n"
        prompt += f"当前心情值：{emotions['mood']}，精力：{emotions['energy']}，紧张度：{emotions['tension']}。\n"
        prompt += f"熟悉度：{relationships['familiarity']}，信任度：{relationships['trust']}。\n"
        if memory:
            prompt += "你记得以下关于用户的信息：\n" + "\n".join(f"- {m}" for m in memory)
        return prompt

    def update_after_chat(self, user_text, bot_reply):
        """每次对话后更新情绪和关系值（记忆池不在这里更新）"""
        emotions = self.data['emotions']
        old_mood = emotions['mood']
        old_energy = emotions['energy']
        old_tension = emotions['tension']
        old_familiarity = self.data['relationships']['familiarity']
        old_trust = self.data['relationships']['trust']

        emotions['mood'] = min(100, emotions['mood'] + 2)
        emotions['energy'] = max(0, emotions['energy'] - 3)
        emotions['tension'] = max(0, emotions['tension'] - 1)

        relationships = self.data['relationships']
        relationships['familiarity'] = min(100, relationships['familiarity'] + 1)
        relationships['trust'] = min(100, relationships['trust'] + 0.5)

        self.data['rhythms']['last_chat_time'] = datetime.now().isoformat()

        # 打印更新结果
        print("\n===== AI状态更新（对话后） =====")
        print(f"心情: {old_mood} -> {emotions['mood']}")
        print(f"精力: {old_energy} -> {emotions['energy']}")
        print(f"紧张度: {old_tension} -> {emotions['tension']}")
        print(f"熟悉度: {old_familiarity} -> {relationships['familiarity']}")
        print(f"信任度: {old_trust} -> {relationships['trust']}")
        print(f"上次对话时间: {self.data['rhythms']['last_chat_time']}")

        self.save()

    def record_health_activity(self):
        """健康记录时调用：更新节律，可能影响情绪"""
        now = datetime.now()
        self.data['rhythms']['last_health_record'] = now.isoformat()

        old_mood = self.data['emotions']['mood']
        last = self.data['rhythms'].get('last_health_record')
        if last:
            last_dt = datetime.fromisoformat(last)
            if now - last_dt > timedelta(hours=24):
                self.data['emotions']['mood'] = max(0, self.data['emotions']['mood'] - 10)

        print("\n===== AI状态更新（健康记录） =====")
        print(f"心情变化: {old_mood} -> {self.data['emotions']['mood']}")
        print(f"最近健康记录时间: {self.data['rhythms']['last_health_record']}")

        self.save()

    def record_account_activity(self):
        """记账时调用：更新节律，可能影响情绪"""
        now = datetime.now()
        self.data['rhythms']['last_account_record'] = now.isoformat()

        old_mood = self.data['emotions']['mood']
        last = self.data['rhythms'].get('last_account_record')
        if last:
            last_dt = datetime.fromisoformat(last)
            if now - last_dt > timedelta(hours=24):
                self.data['emotions']['mood'] = max(0, self.data['emotions']['mood'] - 8)

        print("\n===== AI状态更新（记账记录） =====")
        print(f"心情变化: {old_mood} -> {self.data['emotions']['mood']}")
        print(f"最近记账时间: {self.data['rhythms']['last_account_record']}")

        self.save()

    def update_memory_pool(self, conversation_history):
        """
        关闭软件时调用，结合对话历史更新长期记忆池。
        简单实现：提取用户消息作为潜在记忆，合并后截断到固定条数。
        """
        potential = []
        for msg in conversation_history:
            if msg['role'] == 'user' and len(msg['content']) > 4:
                potential.append(msg['content'])

        old_memory = self.data['memory'].copy()
        combined = self.data['memory'] + potential
        self.data['memory'] = combined[-10:]  # 只保留最近10条

        print("\n===== 记忆池更新 =====")
        print(f"原有记忆条数: {len(old_memory)}")
        print(f"新提取候选: {len(potential)} 条")
        print("更新后记忆池内容:")
        for i, mem in enumerate(self.data['memory'], 1):
            print(f"  {i}. {mem}")

        self.save()

