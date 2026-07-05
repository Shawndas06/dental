SERVICE_VISIT_TYPES: dict[str, str] = {
    "svc_primary": "primary_consultation",
    "svc_secondary": "secondary_visit",
    "svc_hygiene": "hygiene",
    "svc_extraction": "extraction",
    "svc_caries": "treatment",
}


def visit_type_for_service(service_id: str) -> str:
    return SERVICE_VISIT_TYPES.get(service_id, "primary_consultation")
