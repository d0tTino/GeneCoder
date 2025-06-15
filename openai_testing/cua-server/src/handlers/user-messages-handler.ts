import { ModelInput } from "../services/openai-cua-client";
import logger from "../utils/logger";
import { Socket } from "socket.io";
import { sendInputToModel } from "../services/openai-cua-client";
import { computerUseLoop } from "../lib/computer-use-loop";
export async function handleSocketMessage(
  socket: Socket,
  msg: string
): Promise<void> {
  logger.debug(`Server received message: ${msg}`);

  // A message from user resumes the test script or instructs model to take an action.
  const page = socket.data.page;
  const previousResponseId = socket.data.previousResponseId;
  const testCaseReviewAgent = socket.data.testCaseReviewAgent;

  const screenshot = await page.screenshot();
  const screenshotBase64 = screenshot.toString("base64");

  const lastCallId = socket.data.lastCallId;
  const modelInput: ModelInput = {
    screenshotBase64: screenshotBase64,
    previousResponseId: previousResponseId,
    lastCallId: lastCallId,
  };

  const resumeResponse = await sendInputToModel(modelInput, msg);

  const response = await computerUseLoop(
    page,
    resumeResponse,
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
}
