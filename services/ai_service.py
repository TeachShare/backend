import os
from groq import Groq
from dotenv import load_dotenv

class AIService:
    def __init__(self):
        load_dotenv()
        self._client = None
        self.model = "llama-3.3-70b-versatile"

    @property
    def api_key(self):
        key = os.getenv("GROQ_API_KEY")
        if not key:
            return None
        # Remove whitespace and also strip any quotes that might be in the string
        return key.strip().strip('"').strip("'")

    @property
    def client(self):
        if self._client is None:
            key = self.api_key
            if not key:
                raise ValueError("GROQ_API_KEY is not set")
            self._client = Groq(api_key=key)
        return self._client

    def generate_content(self, content_type, subject, grade, objectives):
        # Fallback if key is missing
        current_key = self.api_key
        if not current_key:
            return f"# [Simulated AI Response for {content_type.capitalize()}]\n**Subject**: {subject}\n**Grade**: {grade}\n**Objectives**: {objectives}\n\nPlease set GROQ_API_KEY to see real AI content."

        system_prompts = {
            "lesson": f"You are an expert educator. Create a detailed Lesson Plan for {subject} at the {grade} level. Focus on these objectives: {objectives}. Use Markdown formatting with clear H2 and H3 headers, bold text for emphasis, and bulleted lists. Include sections for: Topic, Duration, Learning Objectives, Materials Needed, Introduction, Main Activities, and Assessment. Make it visually structured.",
            "strategy": f"You are an expert pedagogical consultant. Suggest innovative Teaching Strategies for {subject} at the {grade} level. Focus on these goals: {objectives}. Use Markdown formatting. Provide practical, engaging techniques with clear headings and numbered lists for implementation steps.",
            "classroom": f"You are an expert instructional designer. Create Classroom Materials (like a worksheet structure or activity sheet) for {subject} at the {grade} level. Focus on: {objectives}. Use Markdown. Make it clear and age-appropriate with sections for Instructions, Questions, and Activities."
        }

        prompt = system_prompts.get(content_type, "You are a helpful education assistant.")

        try:
            response = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Generate content for: {objectives}"}
                ],
                model=self.model,
                temperature=0.7,
                max_tokens=2048,
                top_p=0.8
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"Groq API Error: {str(e)}")
            raise e
