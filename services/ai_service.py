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
            "lesson": (
                f"You are an expert educator. Create a detailed Lesson Plan for {subject} at the {grade} level. "
                f"Focus on: {objectives}. \n\n"
                "STRUCTURE REQUIREMENTS:\n"
                "1. Use exactly 5 main sections with '## ' (H2 headers): 'Overview', 'Learning Objectives', 'Materials & Preparation', 'Instructional Procedure', and 'Assessment'.\n"
                "2. Use '### ' (H3 headers) only for sub-steps within the Instructional Procedure.\n"
                "3. Use bulleted lists for objectives and materials.\n"
                "4. Do NOT use '#' (H1) or more than two levels of headers.\n"
                "5. Ensure the content is professional, detailed, and visually structured."
            ),
            "strategy": (
                f"You are an expert pedagogical consultant. Suggest innovative Teaching Strategies for {subject} at the {grade} level. "
                f"Focus on: {objectives}. \n\n"
                "STRUCTURE REQUIREMENTS:\n"
                "1. Use '## ' (H2 headers) for: 'Strategy Summary', 'Pedagogical Foundation', 'Implementation Steps', and 'Expected Outcomes'.\n"
                "2. Use numbered lists for implementation steps.\n"
                "3. Keep the layout clean and avoid excessive nesting of headers.\n"
                "4. Provide practical, engaging techniques."
            ),
            "classroom": (
                f"You are an expert instructional designer. Create Classroom Materials for {subject} at the {grade} level. "
                f"Focus on: {objectives}. \n\n"
                "STRUCTURE REQUIREMENTS:\n"
                "1. Use '## ' (H2 headers) for: 'Instructions', 'Core Activities', 'Practice Questions', and 'Extension Tasks'.\n"
                "2. Make the language age-appropriate for {grade}.\n"
                "3. Use clear separators and lists to make it easy for students to follow."
            )
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
