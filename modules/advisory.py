import os
import json
from google import genai
from google.genai import types


def get_grap_stage(aqi: float) -> str:
    """Maps live AQI to the official Delhi CAQM Graded Response Action Plan (GRAP)."""
    if aqi <= 200:
        return "STATUS NORMAL: No GRAP restrictions active."
    elif aqi <= 300:
        return "GRAP STAGE I (Poor): Enforce vehicle PUC norms, strictly penalize open waste burning, mechanical road sweeping."
    elif aqi <= 400:
        return "GRAP STAGE II (Very Poor): Ban non-essential Diesel Generators (DG), pause minor C&D (Construction & Demolition) work."
    elif aqi <= 450:
        return "GRAP STAGE III (Severe): Ban BS-III Petrol and BS-IV Diesel 4-wheelers, halt all major construction."
    else:
        return "GRAP STAGE IV (Severe+): Ban heavy truck entry (except essentials), halt all C&D, mandate 50% WFH for offices."

def generate_multi_agent_advisory(station_name: str, aqi_value: float, weather_context: str) -> dict:
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    active_grap_mandate = get_grap_stage(float(aqi_value))
    
    fallback_response = {
        "analyst": f"Critical AQI of {aqi_value} detected at {station_name}. Meteorological context ({weather_context}) indicates sustained exposure risk.",
        "enforcement": f"1. ENFORCING {active_grap_mandate.split(':')[0]}: Deploy mobile units to strictly execute mandated CAQM restrictions.\n\n2. Establish perimeter checkpoints for heavy-duty commercial transit compliance.",
        "hindi_translation": f"1. {active_grap_mandate.split(':')[0]} लागू करना: अनिवार्य प्रतिबंधों को लागू करने के लिए मोबाइल इकाइयां तैनात करें।\n\n2. अनुपालन के लिए परिधि जांच चौकियां स्थापित करें।"
    }
    
    if not api_key:
        return fallback_response
        
    try:
        client = genai.Client(api_key=api_key)
        prompt = f"""
        Execute a sequential Multi-Agent simulation for city administrators.
        Live Telemetry: Station={station_name}, AQI={aqi_value}, Weather Context={weather_context}.
        
        CRITICAL LEGAL DIRECTIVE:
        The current mandated government policy is: {active_grap_mandate}
        
        Step 1 (Agent 1 - Analyst): Assess the physical severity strictly on AQI and Wind context. Keep it to 2 tactical sentences.
        Step 2 (Agent 2 - Enforcement): Recommend 2 strict, physical actions for city police that DIRECTLY ENFORCE the GRAP directive provided above. You MUST format this as a numbered list and separate the two points with double line breaks (\\n\\n).
        Step 3 (Agent 3 - Translator): Translate Agent 2's actions into professional Hindi. You MUST preserve the numbered list and double line breaks (\\n\\n).
        
        Return ONLY a valid JSON object. Do not include markdown formatting or backticks.
        {{
            "analyst": "...",
            "enforcement": "...",
            "hindi_translation": "..."
        }}
        """
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2)
        )
        return json.loads(response.text)
        
    except Exception as e:
        print(f"AI Engine Error: {e}")
        return fallback_response