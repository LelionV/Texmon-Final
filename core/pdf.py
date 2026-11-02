
"""
Shared PDF-rendering helper used by all Django PDF views.

Uses Playwright with Chromium to generate A4 PDF documents.

Supports:
- HTML and CSS rendering.
- Embedded Base64 images and company logos.
- External and relative resources through base_url.
- Font and image loading before PDF generation.
- Print backgrounds and accurate colours.
- Root/container execution environments.
"""

import os
from pathlib import Path

# Ensure Playwright uses the browser installation available on TalkSasa.
os.environ.setdefault(
    "PLAYWRIGHT_BROWSERS_PATH",
    "/root/.cache/ms-playwright",
)

from playwright.sync_api import sync_playwright


def render_pdf(html_string: str, base_url: str = None) -> bytes:
    """
    Render HTML into A4 PDF bytes using Playwright and Chromium.

    Args:
        html_string: Fully rendered HTML document.
        base_url: Optional base URL for relative CSS, images and resources.

    Returns:
        PDF document as bytes.

    Raises:
        ValueError: If HTML content is empty.
        RuntimeError: If PDF generation fails.
    """

    if not html_string or not html_string.strip():
        raise ValueError("Cannot generate a PDF from empty HTML.")

    browser = None

    try:
        with sync_playwright() as playwright:

            # Launch Chromium with container-compatible arguments.
            browser = playwright.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            )

            context = browser.new_context(
                viewport={
                    "width": 1280,
                    "height": 1600,
                },
                device_scale_factor=1,
                is_mobile=False,
                java_script_enabled=True,
            )

            page = context.new_page()

            page.set_default_timeout(30000)

            # Load the HTML document.
            page.set_content(
                html_string,
                wait_until="load",
                timeout=60000,
                base_url=base_url,
            )

            # Wait for fonts and images to finish loading.
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
                                img.addEventListener(
                                    "load",
                                    resolve,
                                    { once: true }
                                );

                                img.addEventListener(
                                    "error",
                                    resolve,
                                    { once: true }
                                );
                            });
                        })
                    );
                }"""
            )

            # Allow final layout and rendering calculations.
            page.wait_for_timeout(300)

            # Generate A4 PDF.
            pdf_bytes = page.pdf(
                format="A4",
                print_background=True,
                prefer_css_page_size=True,
                display_header_footer=False,
                scale=1,
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

            context.close()

            return pdf_bytes

    except Exception as exc:
        raise RuntimeError(
            f"PDF generation failed using Playwright: {exc}"
        ) from exc

    finally:
        if browser:
            browser.close()
