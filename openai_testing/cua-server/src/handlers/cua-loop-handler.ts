// lib/handlers/playwright-loop-handler.ts
import playwright, { Page } from "playwright";
const { chromium } = playwright;
import logger from "../utils/logger";
import { computerUseLoop } from "../lib/computer-use-loop";
import { Socket } from "socket.io";
import TestScriptReviewAgent from "../agents/test-script-review-agent";
import { setupCUAModel } from "../services/openai-cua-client";
import { LoginService } from "../services/login-service";
import { ModelInput } from "../services/openai-cua-client";

// Read viewport dimensions from .env file with defaults if not set
const displayWidth: number = parseInt(process.env.DISPLAY_WIDTH || "1024", 10);
const displayHeight: number = parseInt(process.env.DISPLAY_HEIGHT || "768", 10);

export async function cuaLoopHandler(
  systemPrompt: string,
  url: string,
  socket: Socket,
  testCaseReviewAgent: TestScriptReviewAgent,
  username: string,
  password: string,
  loginRequired: boolean,
  userInfo?: string
) {
  logger.info("Starting test script execution...");
  socket.emit("message", "Starting test script execution...");

  try {
    const browser = await chromium.launch({
      headless: false,
      env: {},
      args: ["--disable-extensions", "--disable-file-system"],
    });

    logger.debug("Creating new browser instance...");

    socket.emit("message", "Launching browser...");

    const page = await browser.newPage();

    // Set the page as data in the socket.
    socket.data.page = page;

    // Set viewport dimensions using env values
    await page.setViewportSize({ width: displayWidth, height: displayHeight });

    // Navigate to the provided URL from the form.
    await page.goto(url);

    // wait for 2 seconds
    await page.waitForTimeout(2000);

    // Capture an initial screenshot.
    const screenshot_before_login = await page.screenshot();
    const screenshot_before_login_base64 =
      screenshot_before_login.toString("base64");

    // Asynchronously check the status of the test script.
    const testScriptReviewResponsePromise =
      testCaseReviewAgent.checkTestScriptStatus(screenshot_before_login_base64);

    // Asynchronously emit the test script review response to the socket.
    testScriptReviewResponsePromise.then((testScriptReviewResponse) => {
      logger.debug(
        "Sending screenshot before login to Test Script Review Agent"
      );
      socket.emit("testscriptupdate", testScriptReviewResponse);
      logger.trace(
        `Initial test script state emitted: ${JSON.stringify(
          testScriptReviewResponse,
          null,
          2
        )}`
      );
    });

    // Await till network is idle.
    await page.waitForTimeout(2000);

    let modelInput: ModelInput;

    if (loginRequired) {
      // Note to the developer: Different applications will need their own login handlers.
      logger.debug("Login required... proceeding with login.");
      socket.emit("message", "Login required... proceeding with login.");

      const loginService = new LoginService();
      await loginService.fillin_login_credentials(username, password, page);

      logger.trace(
        "Login execution completed... proceeding with test script execution."
      );

      // wait for 5 seconds
      await page.waitForTimeout(5000);

      const screenshot_after_login = await page.screenshot();
      const screenshot_after_login_base64 =
        screenshot_after_login.toString("base64");

      // Asynchronously check the status of the test script.
      const testScriptReviewResponsePromise_after_login =
        testCaseReviewAgent.checkTestScriptStatus(
          screenshot_after_login_base64
        );

      // Asynchronously emit the test script review response to the socket.
      testScriptReviewResponsePromise_after_login.then(
        (testScriptReviewResponse) => {
          logger.debug(
            "Sending screenshot after login to Test Script Review Agent"
          );
          // Emit the test script review response to the socket.
          socket.emit("testscriptupdate", testScriptReviewResponse);
          logger.trace(
            `Test script state emitted after login: ${JSON.stringify(
              testScriptReviewResponse,
              null,
              2
            )}`
          );
        }
      );

      await loginService.click_login_button(page);

      socket.emit(
        "message",
        "Login step executed... proceeding with test script execution."
      );

      modelInput = {
        screenshotBase64: screenshot_after_login_base64,
        previousResponseId: undefined,
        lastCallId: undefined,
      };
    } else {
      // If login is not required, use the screenshot before login.
      modelInput = {
        screenshotBase64: screenshot_before_login_base64,
        previousResponseId: undefined,
        lastCallId: undefined,
      };
    }

    // Start with an initial call (without a screenshot or call_id)
    const userInfoStr = userInfo ?? "";
    let initial_response = await setupCUAModel(systemPrompt, userInfoStr);

    logger.debug(
      `Initial response from CUA model: ${JSON.stringify(
        initial_response,
        null,
        2
      )}`
    );
    logger.debug(`Starting computer use loop...`);

    const response = await computerUseLoop(
      page,
      initial_response,
      testCaseReviewAgent,
      socket
    );

    const messageResponse = response.output.filter(
      (item: any) => item.type === "message"
    );

    if (messageResponse.length > 0) {
      messageResponse.forEach((message: any) => {
        if (Array.isArray(message.content)) {
          message.content.forEach((contentBlock: any) => {
            if (contentBlock.type === "output_text" && contentBlock.text) {
              socket.emit("message", contentBlock.text);
            }
          });
        }
      });
    }
  } catch (error) {
    logger.error(`Error during playwright loop: ${error}`);
  }
}
