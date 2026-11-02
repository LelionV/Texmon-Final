
"""
Shared PDF-rendering helper used by all Django PDF views.

Uses Playwright with Chromium to render HTML/CSS into PDF documents.

Advantages:
- Supports modern HTML and CSS.
- Handles table layouts, page breaks, borders, and typography.
- Supports embedded Base64 images, including company logos.
- Does not depend on GTK, Pango, or Cairo.
- Suitable for quotations, invoices, proformas, and receipts.
"""

from playwright.sync_api import sync_playwright


def render_pdf(html_string: str) -> bytes:
    """
    Render an HTML string to A4 PDF bytes using Playwright and Chromium.

    Args:
        html_string: Fully rendered HTML document.

    Returns:
        PDF document as bytes.

    Raises:
        RuntimeError: If PDF generation fails.
    """
    if not html_string or not html_string.strip():
        raise ValueError("Cannot generate a PDF from empty HTML.")

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()

            try:
                page = browser.new_page(
                    viewport={"width": 1280, "height": 1600},
                    device_scale_factor=1,
                )

                page.set_content(
                    html_string,
                    wait_until="networkidle",
                    timeout=30000,
                )

                # Wait for images, including Base64-embedded logos.
                page.evaluate(
                    """async () => {
                        await document.fonts.ready;

                        const images = Array.from(document.images);

                        await Promise.all(
                            images.map((img) => {
                                if (img.complete) {
                                    return Promise.resolve();
                                }

                                return new Promise((resolve) => {
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
