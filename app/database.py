    # app/database.py

    from .config import init_db, get_db

    # Initialize the database connection
    init_db()

    def get_patient_collection():
        db = get_db()
        return db["patients"]

    def get_doctor_collection():
        db = get_db()
        return db["doctors"]    
    # Add this function to your existing app/database.py file

    def get_medical_records_collection():
        """Returns the MongoDB collection for medical records."""
        db = get_db()
        # Assuming your medical records collection is named 'medical_records'
        return db["medical_records"]