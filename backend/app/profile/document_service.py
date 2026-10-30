from app.common.errors import (
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.common.filestore import FileStore, FileStoreError
from app.common.roles import ADMIN, STUDENT
from app.profile import document_repository, repository
from app.profile.models import StudentDocument


def upload_document(srn, uploaded_file):
    if uploaded_file is None or not uploaded_file.filename:
        raise ValidationError("A document file is required.")

    profile = repository.get_by_srn(srn)
    if profile is None:
        raise NotFoundError("Student profile not found.")

    store = FileStore()

    try:
        saved = store.save(uploaded_file)
    except FileStoreError as exc:
        raise ValidationError(str(exc)) from exc

    document = StudentDocument(
        profile_id=profile.id,
        original_name=saved["original_name"],
        stored_name=saved["stored_name"],
        content_type=saved["content_type"],
        size_bytes=saved["size_bytes"],
    )

    try:
        document_repository.add(document)
    except Exception:
        store.delete(saved["stored_name"])
        raise

    return {
        "id": document.id,
        "srn": srn,
        "filename": document.original_name,
        "content_type": document.content_type,
        "size_bytes": document.size_bytes,
        "uploaded_at": document.uploaded_at.isoformat(),
    }


def get_document(srn, document_id, user, role):
    profile = repository.get_by_srn(srn)
    if profile is None:
        raise NotFoundError("Student profile not found.")

    if role == STUDENT and user.login_id != srn:
        raise ForbiddenError(
            "You do not have permission to access this document."
        )

    if role not in (ADMIN, STUDENT):
        raise ForbiddenError(
            "You do not have permission to access this document."
        )

    document = document_repository.get_by_profile_and_id(
        profile.id, document_id
    )
    if document is None:
        raise NotFoundError("Document not found.")

    return document
