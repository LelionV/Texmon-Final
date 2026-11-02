
"""
Shared template context processors.

Provides company information and an embedded Base64 logo to templates
throughout the site, including shared PDF layouts and the sidebar/navbar.
"""


def company_info(request):
    try:
        from masters.models import CompanyInfo
        company = CompanyInfo.get_solo()
    except Exception:
        company = None

    return {"company_info": company}