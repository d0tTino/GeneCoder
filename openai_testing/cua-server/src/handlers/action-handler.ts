// lib/handlers/action-handler.ts
import { Page } from "playwright";
import logger from "../utils/logger";

export async function handleModelAction(page: Page, action: any): Promise<void> {
  
  logger.trace(`Handling action: ${JSON.stringify(action)}`);
  const actionType = action.type;
  try {
    switch (actionType) {
      case "click": {
        const { x, y, button = "left" } = action;
        logger.trace(`Action: click at (${x}, ${y}) with button '${button}'`);
        await page.mouse.click(x, y, { button });
        break;
      }
      case "double_click": {
        const { x, y, button = "left" } = action;
        logger.trace(`Action: double click at (${x}, ${y}) with button '${button}'`);
        await page.mouse.dblclick(x, y, { button });
        break;
      }
      case "scroll": {
        const { x, y, scrollX, scrollY, scroll_x, scroll_y } = action;
        // Use the camelCase value if available, otherwise fall back to snake_case.
        const effectiveScrollX = scrollX ?? scroll_x;
        const effectiveScrollY = scrollY ?? scroll_y;
        
        logger.trace(
          `Action: scroll at (${x}, ${y}) with offsets (scrollX=${effectiveScrollX}, scrollY=${effectiveScrollY})`
        );
        await page.mouse.move(x, y);
        await page.evaluate(
          ({ scrollX, scrollY }) => window.scrollBy(scrollX, scrollY),
          { scrollX: effectiveScrollX, scrollY: effectiveScrollY }
        );
        break;
      }
      case "keypress": {
        /**
         * Now handles multiple simultaneous keys (e.g. ["CTRL","A"]) 
         * by holding modifiers down and pressing the main key(s).
         */
        const { keys } = action;

        if (!Array.isArray(keys) || keys.length === 0) {
          logger.warn("No keys provided for keypress action");
          return;
        }

        // Normalize recognized modifiers to the names Playwright expects
        const recognizedModifiers = new Set(["SHIFT", "CTRL", "ALT", "META", "CMD"]);

        // Arrays to keep track of which modifiers to hold down, and which keys to press
        const modifiersToPress: string[] = [];
        const mainKeys: string[] = [];

        // Separate out modifiers from main keys
        for (const rawKey of keys) {
          const upperKey = rawKey.toUpperCase();

          if (recognizedModifiers.has(upperKey)) {
            if (upperKey === "SHIFT") modifiersToPress.push("Shift");
            else if (upperKey === "CTRL") modifiersToPress.push("Control");
            else if (upperKey === "ALT") modifiersToPress.push("Alt");
            else if (upperKey === "META" || upperKey === "CMD") modifiersToPress.push("Meta");
          } else {
            mainKeys.push(rawKey);
          }
        }

        // Press down all modifiers
        for (const mod of modifiersToPress) {
          logger.trace(`Modifier key down: '${mod}'`);
          await page.keyboard.down(mod);
        }

        // Press or type each main key
        for (const mk of mainKeys) {
          logger.trace(`Main key press: '${mk}'`);

          const mkUpper = mk.toUpperCase();
          if (mkUpper === "ENTER") {
            await page.keyboard.press("Enter");
          } else if (mkUpper === "SPACE") {
            await page.keyboard.press(" ");
          } else if (mkUpper === "PAGEDOWN") {
            await page.keyboard.press("PageDown");
          } else if (mkUpper === "PAGEUP") {
            await page.keyboard.press("PageUp");
          } else {
            // For any other key, press it as-is.
            await page.keyboard.press(mk);
          }
        }

        // Release all modifiers in reverse order
        for (let i = modifiersToPress.length - 1; i >= 0; i--) {
          const mod = modifiersToPress[i];
          logger.trace(`Modifier key up: '${mod}'`);
          await page.keyboard.up(mod);
        }

        break;
      }
      case "drag": {
        // Extract the drag path from the action
        const { path } = action;
        if (!Array.isArray(path) || path.length < 2) {
          logger.warn("Drag action requires a path with at least two points.");
          return;
        }
        logger.trace(`Action: drag along path: ${JSON.stringify(path)}`);

        // Move to the starting coordinate of the drag path
        const start = path[0];
        await page.mouse.move(start.x, start.y);
        await page.mouse.down();

        // Drag through each subsequent point in the path.
        for (let i = 1; i < path.length; i++) {
          const point = path[i];
          await page.mouse.move(point.x, point.y);
        }

        // Release the mouse button to complete the drag action
        await page.mouse.up();
        break;
      }
      case "type": {
        const { text } = action;
        logger.trace(`Action: type text '${text}'`);
        await page.keyboard.type(text);
        break;
      }
      case "wait": {
        logger.trace(`Action: wait`);
        await page.waitForTimeout(2000);
        break;
      }
      case "screenshot": {
        logger.trace(`Action: screenshot`);
        // Screenshot is handled separately.
        return;
      }
      default:
        logger.error(`Unrecognized action: ${JSON.stringify(action)}`);
        logger.error(`Action not yet implemented: ${actionType}`);
    }
  } catch (error) {
    logger.error(`Error handling action: ${JSON.stringify(action)}, error: ${error}`);
  }
}


export default async function waitForNetworkIdle(page: Page) {
  // Await till network is idle.
  logger.trace("Waiting for network to be idle...")
  await page.waitForLoadState('networkidle');
  logger.trace("Network is idle... proceeding with login.")
}
