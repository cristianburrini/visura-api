import time

from playwright.async_api import Page

from .base import BaseAuthProvider


class CIEAuthProvider(BaseAuthProvider):
    """
    Authentication provider for Carta d'Identità Elettronica (CIE).
    Implements a robust polling mechanism to wait for user's push notification confirmation.
    """

    async def login(self, page: Page, username: str, password: str, page_logger=None) -> None:
        print("[LOGIN_CIE] Navigo alla pagina di login...")
        await page.goto("https://iampe.agenziaentrate.gov.it/sam/UI/Login?realm=/agenziaentrate")
        if page_logger:
            await page_logger.log(page, "goto_login")

        print("[LOGIN_CIE] Clicco 'CIE'...")
        await page.get_by_role("tab", name="CIE").click()
        if page_logger:
            await page_logger.log(page, "tab_cie")

        print("[LOGIN_CIE] Attendo il pulsante 'Entra con CIE'...")
        cie_button = page.get_by_role("link", name="Entra con CIE")
        await cie_button.wait_for(state="visible")

        print("[LOGIN_CIE] Clicco 'Entra con CIE'...")
        await cie_button.click()
        if page_logger:
            await page_logger.log(page, "entra_con_cie")

        print("[LOGIN_CIE] Attendo redirect al Ministero dell'Interno...")
        await page.wait_for_selector("#username")

        print("[LOGIN_CIE] Inserisco username...")
        await page.locator("#username").fill(username)
        if page_logger:
            await page_logger.log(page, "username_filled")

        print("[LOGIN_CIE] Inserisco password...")
        await page.locator("#password").fill(password)
        if page_logger:
            await page_logger.log(page, "password_filled")

        print("[LOGIN_CIE] Clicco 'Procedi'...")
        await page.get_by_role("button", name="Procedi").click()
        if page_logger:
            await page_logger.log(page, "login_submitted")

        # --- Controllo credenziali ---
        print("[LOGIN_CIE] Controllo alert per credenziali errate...")
        await page.wait_for_timeout(2000)
        error_loc = page.locator(
            ".alert-danger, :text('credenziali errate'), :text('autenticazione fallita'), :text('Utente o password errati'), :text('non valid')"
        )
        if await error_loc.count() > 0 and await error_loc.first.is_visible():
            raise Exception("Login fallito: credenziali errate. Interrompo per evitare blocco account.")

        import os

        timeout_seconds = int(os.environ.get("2FA_TIMEOUT_SECONDS", "90"))

        print(f"[LOGIN_CIE] In attesa di conferma notifica su app CieID (hai {timeout_seconds} secondi)...")
        start_time = time.time()
        resend_attempted = False

        while time.time() - start_time < timeout_seconds:
            try:
                # Check for various success/progress buttons
                autorizza_btn = page.get_by_role("button", name="Autorizza")
                prosegui_btn = page.get_by_role("button", name="Prosegui")
                ricerca_box = page.get_by_role("textbox", name="Cerca il servizio")
                
                # Check for "Resend notification" link
                resend_link = page.locator("#push_link")

                if await autorizza_btn.count() > 0 and await autorizza_btn.is_visible():
                    print("[LOGIN_CIE] Trovato pulsante 'Autorizza', procedo...")
                    await autorizza_btn.click()
                    await page.wait_for_timeout(2000)
                elif await prosegui_btn.count() > 0 and await prosegui_btn.is_visible():
                    print("[LOGIN_CIE] Trovato pulsante 'Prosegui' (Information Release), procedo...")
                    if page_logger:
                        await page_logger.log(page, "before_prosegui")
                    await prosegui_btn.click()
                    if page_logger:
                        await page_logger.log(page, "after_prosegui")
                    break
                elif await ricerca_box.count() > 0 and await ricerca_box.is_visible():
                    print("[LOGIN_CIE] Trovata barra di ricerca servizi, siamo nell'area agenzia entrate.")
                    break
                
                # Auto-resend after 45 seconds if no success yet
                elapsed = time.time() - start_time
                if elapsed > 45 and not resend_attempted:
                    if await resend_link.count() > 0 and await resend_link.is_visible():
                        print("[LOGIN_CIE] Notifica non arrivata dopo 45s, provo a inviarne una nuova...")
                        await resend_link.click()
                        resend_attempted = True
                        if page_logger:
                            await page_logger.log(page, "resend_notification_clicked")
                        await page.wait_for_timeout(3000)

                if await error_loc.count() > 0 and await error_loc.first.is_visible():
                    # Check if it was just a transient error or a real failure
                    error_text = await error_loc.first.inner_text()
                    print(f"[LOGIN_CIE] Alert rilevato: {error_text}")
                    if "scaduta" in error_text.lower() or "annullato" in error_text.lower():
                        raise Exception(f"Login fallito: {error_text}")
            except Exception as e:
                if "Execution context was destroyed" not in str(
                    e
                ) and "Target page, context or browser has been closed" not in str(e):
                    # Se è un'eccezione lanciata da noi (per login fallito), ri-lanciamola
                    if "Login fallito" in str(e):
                        raise
                    print(f"[LOGIN_CIE] Eccezione ignorata durante il polling: {e}")

            await page.wait_for_timeout(1000)
        else:
            raise Exception(
                f"Timeout 2FA: attesa di {timeout_seconds} secondi scaduta senza ricevere la conferma sull'app CieID."
            )

        # Login completato, ora il controllo passa a utils.py per la navigazione SISTER
        print("[LOGIN_CIE] Autenticazione CIE completata con successo.")
        if page_logger:
            await page_logger.log(page, "cie_auth_success")
