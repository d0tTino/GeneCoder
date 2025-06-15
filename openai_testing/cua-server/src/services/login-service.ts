// ────────────────────────────────────────────────────────────────
// lib/services/login-service.ts
/**
 * Fills the generic “Username / Password” form and completes login.
 * Works with the demo page implemented in /login/page.tsx.
 */

import logger from "../utils/logger";
import { Page } from "playwright";

export class LoginService {
  /**
   * Fill the Username + Password fields.
   */
  async fillin_login_credentials(
    username: string,
    password: string,
    page: Page
  ): Promise<boolean> {
    try {
      /* Username */
      await page
        .getByPlaceholder("Username")
        .first()
        .fill(username, { timeout: 5_000 });

      /* Password */
      await page
        .getByPlaceholder("Password")
        .first()
        .fill(password, { timeout: 5_000 });

      logger.debug("Login credentials filled in.");
      return true;
    } catch (error) {
      logger.error("❌ Error filling login credentials:", error);
      return false;
    }
  }

  /**
   * Click the “Login” button and wait for the router to navigate
   * to “/home” (or at least for the network to go idle).
   */
  async click_login_button(page: Page): Promise<boolean> {
    try {
      /* Playwright’s role query works well here */
      const loginBtn = page
        .getByRole("button", { name: /log\s?in/i })
        .first();

      await Promise.all([
        /* Either the URL becomes “/home”… */
        page.waitForURL("**/home", { timeout: 10_000 }).catch(() => {}),
        /* …or network goes idle (fallback) */
        page.waitForLoadState("networkidle", { timeout: 10_000 }),
        loginBtn.click(),
      ]);

      logger.debug("Login successful – navigation finished.");
      return true;
    } catch (error) {
      logger.error("❌ Error clicking login button:", error);
      return false;
    }
  }
}
