import base64
import mimetypes


def get_company_document_context(company_info):
    """Return shared company details and an embedded logo for PDF templates."""
    logo_base64 = ""

    if company_info and company_info.logo:
        try:
            logo_file = company_info.logo
            logo_file.open("rb")

            try:
                logo_bytes = logo_file.read()
            finally:
                logo_file.close()

            if logo_bytes:
                mime_type = (
                    mimetypes.guess_type(logo_file.name)[0]
                    or "application/octet-stream"
                )

                if mime_type.startswith("image/"):
                    encoded = base64.b64encode(logo_bytes).decode("ascii")
                    logo_base64 = f"data:{mime_type};base64,{encoded}"

        except (OSError, ValueError):
            logo_base64 = ""

    return {
        "company_info": company_info,
        "logo_base64": logo_base64,
    }