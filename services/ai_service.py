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

    def analyze_document_metadata(self, files_content, valid_subjects=None, valid_grades=None, valid_types=None):
        """
        Analyzes multiple document contents and returns structured metadata as JSON.
        Includes per-file analysis ('file_labels') to understand each document's role.
        """
        if not self.api_key:
            return {
                "title": "Document Analysis Result",
                "description": "Please set GROQ_API_KEY to enable AI document analysis.",
                "tags": ["analysis", "ai"],
                "subject": "General",
                "grade": "All Grades",
                "duration": "45 Minutes",
                "type": "Lesson Plan",
                "file_labels": []
            }

        # Format reference lists for the prompt
        subjects_str = ", ".join(valid_subjects) if valid_subjects else "General"
        grades_str = ", ".join(valid_grades) if valid_grades else "All Grades"
        types_str = ", ".join(valid_types) if valid_types else "Lesson Plan"

        # Construct the multi-file text block
        # Aggressive truncation for multi-file to stay within context limits
        truncation_limit = 2000 if len(files_content) == 1 else 1200
        combined_text_block = ""
        for item in files_content:
            filename = item.get('filename', 'Unknown File')
            text = item.get('text', '')
            combined_text_block += f"\nFILE: {filename}\nCONTENT:\n{text[:truncation_limit]}\n---\n"

        prompt = (
            "You are an expert instructional designer. I have uploaded multiple educational documents that belong to ONE resource collection. "
            "Your task is to analyze ALL of them and synthesize a single, unified set of metadata in JSON format.\n\n"
            "PHASE 1: INDIVIDUAL FILE AUDIT\n"
            "Identify the specific purpose of every file listed. Do not skip any.\n\n"
            "PHASE 2: UNIFIED SYNTHESIS\n"
            "Create metadata that represents the ENTIRE COLLECTION. \n"
            "- The 'title' must be broad enough to cover all files.\n"
            "- The 'subject', 'grade', and 'type' must be the most accurate common denominators.\n\n"
            "REQUIREMENTS:\n"
            "1. 'file_labels': Array of { 'filename': string, 'analysis': string } for EVERY file.\n"
            "2. 'title': A professional, collective title.\n"
            "3. 'description': A summary of the ENTIRE resource set.\n"
            "4. 'tags': 5-7 keywords covering the scope.\n"
            f"5. 'subject': Match from: [{subjects_str}].\n"
            f"6. 'grade': Match from: [{grades_str}].\n"
            "7. 'duration': Total estimated time.\n"
            f"8. 'type': Primary type from: [{types_str}].\n\n"
            "OUTPUT FORMAT: Return ONLY a valid JSON object. No markdown, no preambles.\n\n"
            f"DOCUMENTS TO ANALYZE:\n{combined_text_block}"
        )

        try:
            response = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a professional educational data parser. Output ONLY JSON."},
                    {"role": "user", "content": prompt}
                ],
                model=self.model,
                temperature=0.2,
                response_format={"type": "json_object"},
                timeout=30 # Add timeout to prevent hanging
            )
            
            raw_content = response.choices[0].message.content
            
            # Robust JSON parsing
            import json
            import re
            try:
                # Sometimes AI wraps JSON in ```json blocks even when told not to
                if "```json" in raw_content:
                    json_str = re.search(r'```json\n(.*?)\n```', raw_content, re.DOTALL).group(1)
                    return json.loads(json_str)
                return json.loads(raw_content)
            except Exception as parse_err:
                print(f"JSON Parse Error: {parse_err}. Raw content: {raw_content[:200]}")
                # Fallback: try to find anything that looks like JSON
                match = re.search(r'\{.*\}', raw_content, re.DOTALL)
                if match:
                    return json.loads(match.group(0))
                return None
            
        except Exception as e:
            print(f"Document Analysis Error: {e}")
            return None

    def generate_quiz_json(self, topic, grade, num_questions, question_types):
        """
        Generates a structured educational quiz in JSON format.
        """
        if not self.api_key:
            # Simulated response for dev mode
            return {
                "title": f"Quiz on {topic}",
                "description": f"A comprehensive quiz about {topic} for {grade} level.",
                "questions": [
                    {
                        "text": f"Sample question about {topic} 1?",
                        "type": "multiple_choice",
                        "options": ["Option A", "Option B", "Option C", "Option D"],
                        "correct_answer": "Option A",
                        "points": 1
                    },
                    {
                        "text": f"Sample question about {topic} 2?",
                        "type": "true_false",
                        "options": ["True", "False"],
                        "correct_answer": "True",
                        "points": 1
                    }
                ]
            }

        types_str = ", ".join(question_types)
        prompt = (
            f"You are an expert instructional designer. Create a {num_questions}-question quiz on the topic: '{topic}' "
            f"suitable for {grade} students.\n\n"
            "REQUIREMENTS:\n"
            f"1. Include these question types: [{types_str}].\n"
            "2. For 'multiple_choice', provide exactly 4 options.\n"
            "3. For 'true_false', the options MUST be ['True', 'False'].\n"
            "4. For 'short_answer', provide a brief sample correct answer or grading key in 'correct_answer'.\n"
            "5. Ensure the difficulty is appropriate for {grade} level.\n"
            "6. Provide a professional 'title' and 'description' for the quiz.\n\n"
            "OUTPUT FORMAT: Return ONLY a valid JSON object with this structure:\n"
            "{\n"
            "  \"title\": \"string\",\n"
            "  \"description\": \"string\",\n"
            "  \"questions\": [\n"
            "    {\n"
            "      \"text\": \"string\",\n"
            "      \"type\": \"multiple_choice\" | \"true_false\" | \"short_answer\",\n"
            "      \"options\": [\"string\"] | null,\n"
            "      \"correct_answer\": \"string\",\n"
            "      \"points\": number\n"
            "    }\n"
            "  ]\n"
            "}"
        )

        try:
            response = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a professional quiz generator. Output ONLY valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                model=self.model,
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            
            import json
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            print(f"Quiz Generation Error: {e}")
            return None
