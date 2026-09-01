# ai_manager.py
import json
import os
import requests  # 需安装：pip install requests
from ai_state import AIState

class AIManager:
    def __init__(self):
        self.ai_state = AIState()
        self.config = self.load_config()
        self.food_db = self.load_db('food_calories.json')
        self.exercise_db = self.load_db('exercise_calories.json')

    def load_config(self):
        """加载 AI 配置（密钥等）"""
        config_path = os.path.join(os.getcwd(), 'ai_config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"api_key": "", "base_url": "https://api.deepseek.com/v1"}

    def load_db(self, filename):
        """加载 JSON 数据库文件"""
        path = os.path.join(os.getcwd(), filename)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def save_db(self, filename, data):
        """保存 JSON 数据库文件"""
        path = os.path.join(os.getcwd(), filename)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def query_deepseek(self, prompt):
        api_key = self.config.get('api_key', '')
        base_url = self.config.get('base_url', 'https://api.deepseek.com/v1')
        if not api_key:
            print("警告：未配置 API 密钥，无法调用 AI 查询。")
            return None

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        # 使用 AIState 构造 system message
        system_msg = self.ai_state.get_system_prompt()
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }
        try:
            resp = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=10)
            resp.raise_for_status()
            result = resp.json()
            content = result['choices'][0]['message']['content']
            return content
        except Exception as e:
            print(f"AI 查询失败：{e}")
            return None

    def get_food_calories(self, food_name):
        """获取食物热量（每100克或每份），若库中无则调用 AI"""
        if food_name in self.food_db:
            return self.food_db[food_name]

        prompt = f"请查询食物“{food_name}”的热量（千卡/100克），只返回 JSON 格式：{{\"calories\": 数值}}"
        result = self.query_deepseek(prompt)
        if result:
            try:
                data = json.loads(result)
                calories = data.get('calories')
                if calories is not None:
                    self.food_db[food_name] = calories
                    self.save_db('food_calories.json', self.food_db)
                    return calories
            except:
                pass
        return None  # 查询失败，返回 None

    def get_exercise_consumption(self, exercise_name):
        """获取运动消耗（千卡/30分钟），若库中无则调用 AI"""
        if exercise_name in self.exercise_db:
            return self.exercise_db[exercise_name]

        prompt = f"请查询运动“{exercise_name}”的消耗热量（千卡/30分钟），只返回 JSON 格式：{{\"calories\": 数值}}"
        result = self.query_deepseek(prompt)
        if result:
            try:
                data = json.loads(result)
                calories = data.get('calories')
                if calories is not None:
                    self.exercise_db[exercise_name] = calories
                    self.save_db('exercise_calories.json', self.exercise_db)
                    return calories
            except:
                pass
        return None