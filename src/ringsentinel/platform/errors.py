"""Public errors never contain internal exception strings."""

ERRORS = {
    "MODEL_VERSION_UNAVAILABLE": (
        503,
        "This run's model version is unavailable. Contact the operator before retrying.",
    ),
    "DISPATCH_FAILED": (
        503,
        "Background analysis could not be delivered. Contact the operator before retrying.",
    ),
    "CAPACITY_TIMEOUT": (
        503,
        "Analysis did not start in time. Retry after capacity becomes available.",
    ),
    "QUOTA_EXCEEDED": (429, "An operational limit was reached. Contact the operator."),
    "RESULT_TRANSPORT_REQUIRED": (
        409,
        "This result requires fragment transport. "
        "Use the authenticated result manifest and chunks.",
    ),
    "INVALID_REQUEST": (400, "The request is not permitted."),
    "METHOD_NOT_ALLOWED": (405, "This HTTP method is not supported."),
    "VALIDATION_ERROR": (422, "Request validation failed."),
    "UNAUTHORIZED": (401, "A valid session is required."),
    "FORBIDDEN": (403, "This operation is not permitted."),
    "NOT_FOUND": (404, "Resource not found."),
    "CONFLICT": (409, "The request conflicts with the current resource state."),
    "UPLOAD_TOO_LARGE": (413, "The dataset exceeds the configured upload limit."),
    "UPLOAD_TRANSPORT_UNAVAILABLE": (409, "Chunked upload is not enabled for this workspace."),
    "INVALID_DATASET": (422, "Supply a valid payments-v1 or DatasetBundle JSON file."),
    "ANALYSIS_FAILED": (500, "Analysis could not be completed."),
    "ANALYSIS_TIMEOUT": (504, "Analysis exceeded its execution time limit."),
    "WORKER_INTERRUPTED": (503, "Analysis was interrupted. Start a new run to retry."),
    "QUEUE_EXPIRED": (409, "Queued analysis expired before execution. Start a new run to retry."),
    "PROVIDER_UNAVAILABLE": (503, "The optional explanation provider is unavailable."),
    "NOT_READY": (503, "Required application dependencies are not ready."),
    "INTERNAL_ERROR": (500, "The request could not be completed."),
}


class ProductError(Exception):
    def __init__(self, code: str):
        self.code = code
        self.status, self.message = ERRORS[code]
        super().__init__(self.message)
