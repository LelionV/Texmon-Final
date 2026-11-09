
"""
Shared PDF rendering helper for Django PDF views.

Uses Playwright and Chromium to generate A4 PDF documents.
Suitable for quotations, invoices, proformas and receipts.
"""

from playwright.sync_api import sync_playwright


def render_pdf(html_string: str) -> bytes:
    """
    Convert rendered HTML into PDF bytes using Chromium.
    """

    if not html_string or not html_string.strip():
        raise ValueError("Cannot generate PDF from empty HTML.")

    browser = None

    try:
        with sync_playwright() as playwright:

            browser = playwright.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )

            page = browser.new_page(
                viewport={
                    "width": 1280,
                    "height": 1600,
                },
                device_scale_factor=1,
            )

            # IMPORTANT:
            # Do not pass base_url. Playwright does not support it.
            page.set_content(
                html_string,
                wait_until="load",
                timeout=60000,
            )

            # Wait for fonts and images.
            page.evaluate(
                """async () => {
                    await document.fonts.ready;

                    await Promise.all(
                        Array.from(document.images).map(img => {
                            if (img.complete) {
                                return Promise.resolve();
                            }

                            return new Promise(resolve => {
                                img.addEventListener("load", resolve, {
                                    once: true
                                });

                                img.addEventListener("error", resolve, {
                                    once: true
                                });
                            });
                        })
                    );
                }"""
            )

            page.emulate_media(media="print")

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
                    "Chromium did not generate a valid PDF."
                )

            return pdf_bytes

    except Exception as exc:
        raise RuntimeError(
            f"Playwright PDF generation failed: {exc}"
        ) from exc

    finally:
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
