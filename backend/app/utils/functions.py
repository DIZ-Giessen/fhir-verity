"""All reusable Function"""


# Check if Patient Pseudonym
def is_valid_patient_id(id_str: str) -> bool:
    """
    Checks if the given patient ID string is valid and pseudonymized.

    Args:
        id_str (str): The patient ID string to validate.

    Returns:
        bool: True if the patient ID is valid and pseudonymized, False otherwise.
    """
    if not id_str:
        return False
    return not (id_str.startswith("20") and len(id_str) == 9)


# Check If Encounter Pseudonym
def is_valid_enc_id(id_str: str) -> bool:
    """
    Checks whether the given Encounter ID is valid and pseudonymized.

    Args:
        id_str (str): The Encounter ID string to validate.

    Returns:
        bool: True if the Encounter ID is valid and pseudonymized, False otherwise.
    """
    if not id_str:
        return False
    return not (id_str.startswith("20") and len(id_str) == 10)
