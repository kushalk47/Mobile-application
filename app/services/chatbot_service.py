# app/services/chatbot_service.py
import os
import google.generativeai as genai
from dotenv import load_dotenv
import logging
import json
from datetime import datetime  # Import datetime for date formatting
import asyncio  # Import asyncio for running synchronous code in a thread
from typing import Dict, Any, Optional # Import for type hinting


# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Configure the Generative AI model
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    logger.error("GEMINI_API_KEY not found in environment variables.")
    raise ValueError("GEMINI_API_KEY not found. Please set it in your .env file or environment.")

try:
    genai.configure(api_key=API_KEY)
    # Define the single model name to be used for all tasks
    # Defaulting to gemini-1.5-flash-latest
    SINGLE_MODEL_NAME = os.getenv("SINGLE_MODEL_NAME", "gemini-1.5-flash-latest")

    # We will initialize the model within the class __init__

except Exception as e:
    logger.error(f"Error configuring Google Generative AI: {e}")
    raise ConnectionError(f"Could not configure Google Generative AI: {e}") from e


class MedicalChatbot:
    """
    A class to manage interactions with a single LLM model for chat, summary, report generation, and structured parsing.
    """
    def __init__(self, model_name: str = SINGLE_MODEL_NAME):
        """
        Initializes the single AI model.

        Args:
            model_name: The name of the generative model to use for all tasks.
        """
        self.model_name = model_name
        self.model = None  # We will use only one model instance

        try:
            # Initialize the single model
            # Using safety_settings to potentially handle cases where model might be blocked
            self.model = genai.GenerativeModel(
                model_name=self.model_name,
                # Optional: Add safety settings if needed
                # safety_settings=[
                #     {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                #     {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                #     {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                #     {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                # ]
            )
            logger.info(f"Chatbot and Report Generation initialized with model: {self.model_name}")

        except Exception as e:
            logger.error(f"Error initializing generative model {self.model_name}: {e}")
            raise ConnectionError(f"Could not initialize generative model {self.model_name}") from e

    def _format_patient_data(self, patient_data: dict) -> str:
        """
        Formats the patient's data into a string suitable for the LLM context.
        This version assumes patient_data includes the nested 'patient' and 'medical_record' keys.
        """
        # Ensure patient_data is structured as {"patient": {...}, "medical_record": {...}}
        patient_info = patient_data.get("patient", {})
        medical_record = patient_data.get("medical_record", {})

        if not patient_info and not medical_record:
            return "No patient data available."

        formatted_data = ""
        if patient_info:
            formatted_data += f"Patient ID: {patient_info.get('_id')}\n"
            formatted_data += f"Name: {patient_info.get('name', {}).get('first', 'N/A')} {patient_info.get('name', {}).get('last', '')}\n"
            formatted_data += f"Email: {patient_info.get('email', 'N/A')}\n"
            formatted_data += f"Age: {patient_info.get('age', 'N/A')}\n"
            formatted_data += f"Gender: {patient_info.get('gender', 'N/A')}\n"
            formatted_data += f"Phone: {patient_info.get('phone_number', 'N/A')}\n"
            formatted_data += "Address: {street}, {city}, {state}, {zip}, {country}\n".format(
                street=patient_info.get('address', {}).get('street', 'N/A'),
                city=patient_info.get('address', {}).get('city', 'N/A'),
                state=patient_info.get('address', {}).get('state', 'N/A'),
                zip=patient_info.get('address', {}).get('zip', 'N/A'),
                country=patient_info.get('address', {}).get('country', 'N/A')
            )
            reg_date = patient_info.get('registration_date')
            if isinstance(reg_date, datetime):
                formatted_data += f"Registration Date: {reg_date.strftime('%Y-%m-%d %H:%M')}\n"
            elif reg_date:
                formatted_data += f"Registration Date: {reg_date}\n"
            dob = patient_info.get('date_of_birth') # Added DOB formatting
            if dob:
                if isinstance(dob, datetime):
                    formatted_data += f"Date of Birth: {dob.strftime('%Y-%m-%d')}\n"
                else: # Assume string format if not datetime
                    formatted_data += f"Date of Birth: {dob}\n"

        formatted_data += "\n--- Medical Record ---\n"
        if medical_record:
            formatted_data += "Allergies: {}\n".format(", ".join(medical_record.get('allergies', ['None'])))

            family_history = medical_record.get('family_medical_history')
            if family_history:
                formatted_data += f"Family Medical History: {family_history}\n"
            else:
                formatted_data += "Family Medical History: None provided.\n"


            medications = medical_record.get('current_medications', [])
            if medications:
                formatted_data += "Current Medications:\n"
                # Check if medication items are dictionaries before trying to access keys
                for med in medications:
                    if isinstance(med, dict):
                        formatted_data += f"- {med.get('name', 'N/A')} ({med.get('dosage', 'N/A')}, {med.get('frequency', 'N/A')})\n"
                    else:
                        formatted_data += f"- {med}\n" # Handle if they are just strings


            diagnoses = medical_record.get('diagnoses', [])
            if diagnoses:
                formatted_data += "Diagnoses:\n"
                # Check if diagnosis items are dictionaries
                for diag in diagnoses:
                    if isinstance(diag, dict):
                        formatted_data += f"- {diag.get('disease', 'N/A')} (Year: {diag.get('year', 'N/A')})\n"
                    else:
                        formatted_data += f"- {diag}\n" # Handle if they are just strings


            # Note: Prescriptions and Consultation History could be lists of dicts or strings depending on how they were saved
            formatted_data += "Prescriptions: {}\n".format("\n".join([str(p) for p in medical_record.get('prescriptions', ['None'])]))
            formatted_data += "Consultation History: {}\n".format("\n".join([str(c) for c in medical_record.get('consultation_history', ['None provided.'])]))


            reports = medical_record.get('reports', [])
            if reports:
                formatted_data += "Reports:\n"
                for report in reports:
                    # Check if report items are dictionaries
                    if isinstance(report, dict):
                        date_obj = report.get('date')
                        date_str = date_obj.strftime('%Y-%m-%d') if isinstance(date_obj, datetime) else (date_obj if date_obj else 'N/A')
                        # Provide the description content to the AI for context
                        description_content = report.get('description', 'Content not available.')
                        formatted_data += f"- {report.get('report_type', 'Report')} on {date_str}: {description_content}\n"
                    else:
                        formatted_data += f"- {report}\n" # Handle if they are just strings


            immunizations = medical_record.get('immunizations', [])
            if immunizations:
                formatted_data += "Immunizations:\n"
                for imm in immunizations:
                    # Check if immunization items are dictionaries
                    if isinstance(imm, dict):
                        imm_date_obj = imm.get('date')
                        imm_date_str = imm_date_obj.strftime('%Y-%m-%d') if isinstance(imm_date_obj, datetime) else (imm_date_obj if imm_date_obj else 'N/A')
                        formatted_data += f"- {imm.get('name', 'Vaccine')} on {imm_date_str} by {imm.get('administered_by', 'N/A')}. Lot: {imm.get('lot_number', 'N/A')}\n"
                    else:
                        formatted_data += f"- {imm}\n" # Handle if they are just strings


        else:
            formatted_data += "No medical record details available.\n"

        return formatted_data

    def _format_doctor_data(self, doctor_data: dict) -> str:
        """
        Formats the doctor's data into a string suitable for the LLM context header.
        """
        if not doctor_data:
            return "No doctor data available."

        formatted_data = f"Doctor Name: Dr. {doctor_data.get('name', {}).get('first', 'N/A')} {doctor_data.get('name', {}).get('last', '')}\n"
        formatted_data += f"Specialty: {doctor_data.get('specialty', 'N/A')}\n"
        formatted_data += f"Contact: {doctor_data.get('phone_number', 'N/A')} | {doctor_data.get('email', 'N/A')}"
        return formatted_data

    async def generate_response(self, patient_data: dict, doctor_query: str) -> str:
        """
        Generates a chatbot response based on patient data and doctor's query.
        Uses the single model instance.
        """
        if not self.model:
            return "AI model is not initialized."

        patient_context = self._format_patient_data(patient_data)

        system_instruction = (
            "You are a helpful medical assistant chatbot designed to assist doctors by answering "
            "questions based on the provided patient medical data. Analyze the patient's data "
            "carefully. Answer the doctor's query using ONLY the information present in the "
            "provided patient data. If the information required to answer the query is not "
            "explicitly present in the data, clearly state that you cannot answer the question "
            "based on the provided information. Do not invent or assume information. "
            "Present the information clearly and concisely."
        )

        full_prompt = f"{system_instruction}\n\nPatient Medical Data:\n{patient_context}\n\nDoctor's Query: {doctor_query}\n\nAssistant Response:"

        try:
            # Run the synchronous generate_content call in a separate thread
            response = await asyncio.to_thread(self.model.generate_content, full_prompt)
            # Explicitly check if text attribute exists and is not None
            if hasattr(response, 'text') and response.text is not None:
                return response.text
            else:
                logger.warning(f"AI model returned an empty or invalid response for chat: {response}")
                return "Sorry, the AI model returned an empty response."

        except Exception as e:
            logger.error(f"Error generating chatbot response: {e}")
            return f"Sorry, I could not generate a response at this time. Error: {type(e).__name__}"

    async def summarize_medical_record(self, patient_data: dict) -> str:
        """
        Generates a summary of the patient's medical record.
        Uses the single model instance.
        """
        if not self.model:
            return "AI model is not initialized for summarization."

        patient_context = self._format_patient_data(patient_data)

        system_instruction = (
            "You are a medical assistant chatbot. Your task is to provide a concise summary "
            "of the provided patient medical data. Highlight key information such as "
            "diagnoses, current medications, known allergies, and significant history. "
            "Present the summary clearly and structured."
        )

        full_prompt = f"{system_instruction}\n\nPatient Medical Data:\n{patient_context}\n\nAssistant Summary:"

        try:
            # Run the synchronous generate_content call in a separate thread
            response = await asyncio.to_thread(self.model.generate_content, full_prompt)
            # Explicitly check if text attribute exists and is not None
            if hasattr(response, 'text') and response.text is not None:
                return response.text
            else:
                logger.warning(f"AI model returned an empty or invalid response for summary: {response}")
                return "Sorry, the AI model returned an empty summary response."

        except Exception as e:
            logger.error(f"Error generating medical record summary: {e}")
            return f"Sorry, I could not generate the summary at this time. Error: {type(e).__name__}"

    async def generate_medical_report(self, patient_data: dict, doctor_data: dict, transcribed_text: str) -> str:
        """
        Formats transcribed text into a medical report using the AI model.
        Uses the single model instance.
        """
        if not self.model:
            return "AI model is not initialized for report generation."

        if not transcribed_text or not transcribed_text.strip():
            return "No transcribed text provided to generate a report."

        patient_context = self._format_patient_data(patient_data)
        doctor_context = self._format_doctor_data(doctor_data)

        prompt_parts = [
            "You are an AI medical assistant. Format the following dictated notes into a structured medical report.",
            "do not Include a header or footer that will be done with the help of report lab .",
            "Present the main content of the dictated notes clearly.",
            "Possible sections could include Subjective (what the patient says), Objective (examination findings, lab results if mentioned), Assessment (diagnosis/impression), and Plan (treatment, follow-up). Organize the dictated notes into these sections if they fit naturally, or present as a clear narrative.",
            "Ensure the output is ONLY the formatted medical report text. Do NOT include any introductory or concluding conversational sentences like 'Here is the report:' or 'I have generated the report.'.",
            "Start directly with the report header.",
            " The output which you give should not have asterisks becuase the formatting can't be done in the report seperate using --> ",
            "\n--- Doctor Information ---",
            doctor_context,
            "\n\n--- Patient Information ---",
            patient_context,
            "\n\n--- Dictated Notes ---",
            transcribed_text,
            "\n\n--- Formatted Medical Report ---",
            "Generate the formatted medical report below:"
        ]

        full_prompt = "\n".join(prompt_parts)
        logger.info(f"Generated prompt for AI model report (partial): {full_prompt[:500]}...")

        formatted_report_text = "Error generating report."
        try:
            # Run the synchronous generate_content call in a separate thread
            response = await asyncio.to_thread(self.model.generate_content, full_prompt)

            # Explicitly check if the response object has a 'text' attribute and if it's not None
            if hasattr(response, 'text') and response.text is not None:
                formatted_report_text = response.text
                logger.info("Successfully generated report text from AI model.")
            else:
                # Handle cases where the model might return a valid response object but no text
                formatted_report_text = "AI model generated no text response."
                logger.warning(f"AI model returned an empty text response: {response}")

        except Exception as e:
            # This catches exceptions during the API call or response processing
            logger.error(f"Error calling AI model for report generation: {e}")
            # Include the type of the exception and the message for better debugging
            formatted_report_text = f"Error communicating with AI model for report generation: {type(e).__name__}: {e}"

        # Return the processed text
        return formatted_report_text.strip()


    # ADDED THIS NEW METHOD for structured parsing - ENSURED INDENTATION
    async def generate_structured_response(self, prompt: str, patient_data: Dict[str, Any], doctor_data: Dict[str, Any]) -> str:
        """
        Sends a structured prompt to the AI model and returns the raw text response.
        This is intended for tasks like entity extraction where the prompt guides the output format.

        Args:
            prompt: The specific prompt designed for structured output (e.g., JSON extraction).
            patient_data: Patient context dictionary.
            doctor_data: Doctor context dictionary.

        Returns:
            The raw text response from the AI model. This response is expected to be
            parsable (e.g., a JSON string).
        """
        # Note: patient_data and doctor_data are included as arguments here for consistency
        # with other methods, but the actual data inclusion in the prompt is handled
        # by the caller (parser_service), which crafts the full prompt string.

        if not self.model:
            return "AI model is not initialized for structured response."

        logger.info("Calling AI for structured response (parsing).")
        try:
            # Run the synchronous generate_content call in a separate thread
            # We are passing the full, self-contained prompt string directly to the model.
            response = await asyncio.to_thread(self.model.generate_content, prompt)

            # Explicitly check if the response object has a 'text' attribute and if it's not None
            if hasattr(response, 'text') and response.text is not None:
                raw_text_output = response.text
                logger.debug(f"AI structured response received: {raw_text_output[:200]}...") # Log start of response
                return raw_text_output
            else:
                logger.warning(f"AI model returned an empty or invalid response for structured task: {response}")
                # Return a string indicating no text was generated
                return "AI model generated no text response for structured task."

        except Exception as e:
            logger.error(f"Error during AI structured response generation: {e}", exc_info=True)
            # Return a string indicating the error
            return f"Error communicating with AI model for structured task: {type(e).__name__}: {e}"


# Example Usage (for testing the class independently)
if __name__ == "__main__":
    import asyncio
    from datetime import datetime

    # Dummy patient data structure (matching the format passed to service methods)
    dummy_patient_data_full = {
        "patient": { # Basic patient info
            "_id": "681326e011b67a6c18bdd8c3",
            "name": {"first": "John", "last": "Doe"},
            "email": "john.doe@example.com",
            "phone_number": "123-456-7890",
            "age": 45,
            "gender": "Male",
            "address": {"street": "123 Main St", "city": "Anytown", "state": "CA", "zip": "91234", "country": "USA"},
            "emergency_contact": {"name": "Jane Doe", "phone": "987-654-3210", "relationship": "Spouse"},
            "registration_date": datetime.utcnow(),
            "date_of_birth": "1980-05-10" # Added DOB
        },
        "medical_record": { # Medical record details
            "allergies": ["Penicillin", "Shellfish"],
            "family_medical_history": "Father had heart disease. Mother has diabetes.",
            "current_medications": [ # Using dict format as expected for parsing
                {"name": "Lisinopril", "dosage": "10mg", "frequency": "daily", "start_date": "2023-01-20", "end_date": None, "notes": "For hypertension"},
                {"name": "Metformin", "dosage": "500mg", "frequency": "twice daily", "start_date": "2022-11-01", "end_date": None, "notes": "For Type 2 Diabetes"}
            ],
            "diagnoses": [ # Using dict format as expected for parsing
                {"disease": "Hypertension", "year": 2022, "diagnosis_date": "2022-10-15", "notes": None},
                {"disease": "Type 2 Diabetes", "year": 2021, "diagnosis_date": "2021-09-01", "notes": None}
            ],
            "prescriptions": [], # Keeping as list of dicts or strings
            "consultation_history": [], # Keeping as list of dicts or strings
            "reports": [ # Keeping as list of dicts
                {"report_type": "Blood Test", "report_id": "R001", "date": datetime(2024, 1, 10), "content_id": "fake_content_id_1", "description": "Cholesterol slightly elevated."},
                {"report_type": "ECG", "report_id": "R002", "date": datetime(2024, 2, 15), "content_id": "fake_content_id_2", "description": "Normal sinus rhythm."}
            ],
            "immunizations": [ # Using dict format as expected for parsing
                {"name": "Flu Shot", "date": datetime(2024, 10, 5), "administered_by": "Dr. Smith", "lot_number": "ABC123"}
            ]
        }
    }


    # Dummy doctor data structure
    dummy_doctor_data = {
        "_id": "doc123", # Added doctor ID
        "name": {"first": "Alice", "last": "Smith"},
        "specialty": "General Practitioner",
        "phone_number": "987-654-3210",
        "email": "alice.smith@example.com"
    }

    async def main():
        try:
            # Ensure logging is configured for the example usage
            logging.basicConfig(level=logging.DEBUG) # Set logging level to DEBUG for example

            chatbot = MedicalChatbot()

            print("--- Chat Example ---")
            query = "What are his known allergies?"
            chat_response = await chatbot.generate_response(dummy_patient_data_full, query)
            print(f"Query: {query}")
            print(f"Response: {chat_response}")

            print("\n--- Summary Example ---")
            summary = await chatbot.summarize_medical_record(dummy_patient_data_full)
            print(summary)

            print("\n--- Report Generation Example ---")
            transcribed_notes = "Patient presented with cough and fever. Examination showed clear lungs. Prescribed rest and fluids."
            report_text = await chatbot.generate_medical_report(dummy_patient_data_full, dummy_doctor_data, transcribed_notes)
            print(f"Transcribed Notes: {transcribed_notes}")
            print(f"Generated Report:\n{report_text}")

            # --- Structured Response Example (for parsing) ---
            print("\n--- Structured Parsing Example ---")
            # This prompt structure comes from the parser_service
            parsing_prompt = f"""
Extract medications and diagnoses from the following text in JSON format:
Text: "The patient was prescribed Amoxicillin 500mg for tonsillitis diagnosed today. They also mentioned a history of hypertension."
JSON Output:
"""
            # Note: We pass the parsing_prompt directly here, as the structured response
            # method is designed to take the *full prompt* from the parser.
            # The dummy patient_data_full and doctor_data are passed for argument consistency,
            # but are not used within generate_structured_response itself
            # because the full prompt is provided by the caller.
            structured_output = await chatbot.generate_structured_response(parsing_prompt, dummy_patient_data_full, dummy_doctor_data)
            print(f"Parsing Prompt (partial): {parsing_prompt[:100]}...")
            print(f"Structured Output:\n{structured_output}")


        except ValueError as e:
            print(f"Configuration Error: {e}")
        except ConnectionError as e:
            print(f"Initialization Error: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

    # Run the async main function
    asyncio.run(main())