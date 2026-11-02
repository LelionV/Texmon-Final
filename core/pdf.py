import re
from html import escape

from playwright.sync_api import sync_playwright


def render_pdf(html_string: str, base_url: str = None) -> bytes:
    """
    Render HTML into an A4 PDF using Playwright and Chromium.
    """

    if not html_string or not html_string.strip():
        raise ValueError("Cannot generate a PDF from empty HTML.")

    if base_url:
        base_tag = f'<base href="{escape(base_url, quote=True)}">'

        if re.search(r"<head[^>]*>", html_string, flags=re.IGNORECASE):
            html_string = re.sub(
                r"(<head[^>]*>)",
                rf"\1{base_tag}",
                html_string,
                count=1,
                flags=re.IGNORECASE,
            )
        elif re.search(r"<html[^>]*>", html_string, flags=re.IGNORECASE):
            html_string = re.sub(
                r"(<html[^>]*>)",
                rf"\1<head>{base_tag}</head>",
                html_string,
                count=1,
                flags=re.IGNORECASE,
            )
        else:
            html_string = f"<head>{base_tag}</head>{html_string}"

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            )

            try:
                page = browser.new_page(
                    viewport={"width": 1280, "height": 1600},
                    device_scale_factor=1,
                )

                page.set_content(
                    html_string,
                    wait_until="load",
                    timeout=60000,
                )

                page.evaluate("""
                    async () => {
                        await document.fonts.ready;

                        await Promise.all(
                            Array.from(document.images).map(img => {
                                if (img.complete) {
                                    return Promise.resolve();
                                }

                                return new Promise(resolve => {
                                    img.addEventListener("load", resolve, {once: true});
                                    img.addEventListener("error", resolve, {once: true});
                                });
                            })
                        );
                    }
                """)

                page.wait_for_timeout(300)

                pdf_bytes = page.pdf(
                    format="A4",
                    print_background=True,
                    prefer_css_page_size=True,
                    display_header_footer=False,
                    margin={
                        "top": "12mm",
                        "right": "14mm",
                        "bottom": "15mm",
                        "left": "14mm",
                    },
                )

                if not pdf_bytes or not pdf_bytes.startswith(b"%PDF"):
                    raise RuntimeError(
                        "Chromium did not return a valid PDF document."
                    )

                return pdf_bytes

            finally:
                browser.close()

    except Exception as exc:
        raise RuntimeError(
            f"PDF generation failed using Playwright: {exc}"
        ) from exc
