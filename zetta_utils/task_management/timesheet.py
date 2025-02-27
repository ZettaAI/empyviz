# pylint: disable=all
import time

from google.cloud import firestore
from typeguard import typechecked

from .exceptions import UserValidationError
from .helpers import get_transaction, retry_transient_errors
from .project import get_firestore_client
from .types import TimesheetEntry


@retry_transient_errors
@typechecked
def submit_timesheet(project_name: str, user_id: str, entry: TimesheetEntry):
    """
    Submit a timesheet entry for the user's active subtask.

    :param project_name: The name of the project
    :param user_id: The ID of the user submitting the timesheet
    :param entry: The timesheet entry data
    :return: True if submission successful
    :raises UserValidationError: If user validation fails
    :raises ValueError: If entry data is invalid
    :raises RuntimeError: If the Firestore transaction fails
    """
    if entry["duration_seconds"] <= 0:
        raise ValueError("Duration must be positive")

    client = get_firestore_client()
    user_ref = client.collection(f"{project_name}_users").document(user_id)

    @firestore.transactional
    def submit_in_transaction(transaction):
        # Get user and verify they have an active subtask
        user_doc = user_ref.get(transaction=transaction)
        if not user_doc.exists:
            raise UserValidationError(f"User {user_id} not found")

        user_data = user_doc.to_dict()
        if not user_data["active_subtask"]:
            raise UserValidationError("User does not have an active subtask")

        # Get the subtask and verify user is assigned
        subtask_ref = client.collection(f"{project_name}_subtasks").document(
            user_data["active_subtask"]
        )
        subtask_doc = subtask_ref.get(transaction=transaction)
        if not subtask_doc.exists:
            raise UserValidationError(f"Subtask {user_data['active_subtask']} not found")

        subtask_data = subtask_doc.to_dict()
        if subtask_data["active_user_id"] != user_id:
            raise UserValidationError("Subtask not assigned to this user")

        # Create timesheet entry
        timesheet_ref = client.collection(f"{project_name}_timesheets").document()
        timesheet_data = {
            **entry,
            "user_id": user_id,
            "subtask_id": user_data["active_subtask"],
            "created_ts": time.time(),
        }
        transaction.set(timesheet_ref, timesheet_data)

        # Update subtask's last_leased_ts
        transaction.update(subtask_ref, {"last_leased_ts": time.time()})

    submit_in_transaction(get_transaction())
